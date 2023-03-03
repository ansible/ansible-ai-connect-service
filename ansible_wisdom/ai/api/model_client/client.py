## WARNING DO NOT COMMIT THIS
## Example for using the gRPC client to connect to MM
from grpc_client import GrpcClient

client = GrpcClient(
  inference_url="localhost:8033",
  management_url=""
) 

if __name__ == "__main__":
    response = client.infer(prompt="install ffmpeg on RHEL 9", context="")
    print(response)
