// Real-world pattern from modelcontextprotocol/servers (src/memory/index.ts) that
// previously false-positived: a zod raw-shape inputSchema with real declared fields,
// but no literal "properties" key anywhere in the source.
server.registerTool(
  "add_observations",
  {
    inputSchema: {
      observations: z.array(z.object({
        entityName: z.string().describe("The name of the entity to add the observations to"),
        contents: z.array(z.string()).describe("An array of observation contents to add")
      }))
    },
    outputSchema: {
      results: z.array(z.object({
        entityName: z.string(),
        addedObservations: z.array(z.string())
      }))
    },
  },
  async ({ observations }) => {
    return { content: [] };
  }
);
