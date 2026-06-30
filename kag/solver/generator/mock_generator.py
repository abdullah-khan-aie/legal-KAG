from kag.interface import GeneratorABC


@GeneratorABC.register("mock_generator")
class MockGenerator(GeneratorABC):
    def invoke(self, query, context):
        results = []
        for task in context.gen_task(False):
            results.append(
                {
                    "action": {"name": task.executor, "arguments": task.arguments},
                    "result": task.result,
                }
            )
        return f"Query: {query}\nOutput: {results}"
