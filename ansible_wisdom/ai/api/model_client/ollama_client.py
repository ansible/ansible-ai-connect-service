import logging
import re

import requests
from django.conf import settings

from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain.text_splitter import MarkdownHeaderTextSplitter, MarkdownTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings.sentence_transformer import (
    SentenceTransformerEmbeddings,
)

from operator import itemgetter

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)



class OllamaClient(ModelMeshClient):
    instance = None
    embeddings = SentenceTransformerEmbeddings()
    #loader = loader = UnstructuredMarkdownLoader("/etc/context/rules.md", mode="single")
    loader = UnstructuredMarkdownLoader("/etc/context/rules-short.md", mode="single")
    docs = loader.load()
    md_splitter = MarkdownTextSplitter()
    docs = md_splitter.split_documents(docs)
    logger.info(f"loaded {len(docs)} documents")

    logger.info("initializing vector store with embeddings")
    vectorstore = FAISS.from_documents(docs, embeddings)
    retriever = vectorstore.as_retriever()
    logger.info("DONE initializing vector store with embeddings")

    def __new__(cls, *args, **kwargs):
        if cls.instance is not None:
            return cls.instance
        instance = super().__new__(cls)
        return instance

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}


    def infer(self, model_input, model_id=None, suggestion_id=None):

        loader = UnstructuredMarkdownLoader("/etc/context/rules-short.md", mode="single")
        docs = loader.load()
        md_splitter = MarkdownTextSplitter()
        docs = md_splitter.split_documents(docs)
        logger.info(f"loaded {len(docs)} documents")

        logger.info("initializing vector store with embeddings")
        vectorstore = FAISS.from_documents(docs, self.embeddings)
        retriever = vectorstore.as_retriever()
        logger.info("DONE initializing vector store with embeddings")

        model_id = model_id or settings.ANSIBLE_AI_MODEL_NAME

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")

        logger.info(f"prompt: '{prompt}'")
        logger.info(f"context: '{context}'")

        llm = Ollama(
            base_url=self._inference_url,
            model=model_id,
            temperature=0.1,
            # num_predict=400,
            # stop=[],
            # repeat_last_n=256,
            # repeat_penalty=1.18,
            # top_k=40,
            # top_p=0.5,
            # tfs_z=1,
            # mirostat=0,
            # mirostat_tau=5,
            # mirostat_eta=0.1,
            cache=False,
        )

        rules = [
            "replace all truthy values, like 'yes', with 'true'",
            "replace all falsey values, like 'no', with 'false",
            #"do not use the yum module to install software on fedora, use the dnf module instead",
            "only use the ansible.builtin.package module to install packages",
            "only use fully-qualified collection names, or fqcn, in your response",
        ]

        #vectorstore = FAISS.from_texts(rules, embedding=SentenceTransformerEmbeddings())
        #embeded_docs = embeddings.embed_documents(docs)

        logger.info("creating template")
        rag_template = """You're an Ansible expert. Return a single task that best completes the following partial playbook:
        {context}{prompt}

        Return only the task as YAML.
        Do not return multiple tasks.
        Do not explain your response.

        Understand and apply the following rules to create the task:
        {rules}
        """

        rag_template = """You're an Ansible expert. Return only the Ansible code that best completes the following partial playbook:
        {context}{prompt}

        Return only YAML.
        Do not explain your response.

        Understand and apply the following rules to create the task; when you see a prompt that resembles the Problematic Code, make it look like the Correct Code:
        {rules}
        """

        rag_template = """You're an Ansible expert. Return only the Ansible code that best completes the following partial playbook:
        {context}{prompt}

        Return only YAML.
        Do not explain your response.

        Understand and apply the following rules to create the task.
        Change the task to resemble the Correct Code if, and only if, the task resembles the Problematic Code:
        {rules}
        """

        playbook_template = """You're an Ansible expert. Return only the Ansible code that best completes the following partial playbook:
        {context}{prompt}

        Return only YAML.
        Do not explain your response.

        Understand and apply the following rules to create the task:
        {rules}
        """

        template = """You're an Ansible expert. Return a single task that best completes the following partial playbook:
        {context}{prompt}

        Return only the task as YAML.
        Do not return multiple tasks.
        Do not explain your response.

        Apply the following rules to create the task:
        {rules}
        """

        #template = PromptTemplate.from_template(playbook_template)
        template = PromptTemplate.from_template(rag_template)

        # Only return the portion of the task that comes after the '- name: this is the name'.
        try:
            logger.info(f"constructing chain")
            chain = (
                {
                    "context": itemgetter("context"),
                    "rules": itemgetter("rules") | retriever,
                    #"rules": itemgetter("rules"),
                    "prompt": itemgetter("prompt"),
                }
                | template | llm
            )

            #chain = template | llm

            logger.info(f"invoking chain")
            task = chain.invoke(
                {
                    "context": context,
                    #"rules": rules,
                    #"rules": "what are the rules?",
                    "rules": f"what are the rules?",
                    "prompt": prompt
                }
            )

            logger.info(f"response: {task}")

            # TODO(rg): remove when we have a better tune/prompt

            task = task.split("```yaml")[-1]
            task = re.split(r"- name:.+\n", task)[-1]
            task = task.split("```")[0]

            logger.info(f"task: {task}")
            logger.info(f"model: {model_id}")
            response = {"predictions": [task], "model_id": model_id}

            return response
        except requests.exceptions.Timeout:
            raise ModelTimeoutError
