const editor = {
  create: () => {
    return {
      dispose: () => {},
    }
  },
  defineTheme: function() {}
};

const monaco = {
  editor,
  languages: {json: {jsonDefaults: { setDiagnosticsOptions: function () {}}}}
};

module.exports = monaco;
