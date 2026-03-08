// Stub for mermaid module — prevents vue-stream-markdown from throwing
// "Mermaid module is not available" when mermaid is not installed.
const mermaid = {
  initialize: () => {},
  run: async () => {},
  render: async (_id: string, _code: string) => ({ svg: '', bindFunctions: () => {} }),
  parse: async () => {},
  mermaidAPI: {
    initialize: () => {},
    render: async (_id: string, _code: string) => ({ svg: '' }),
  },
  contentLoaded: () => {},
}

export default mermaid
