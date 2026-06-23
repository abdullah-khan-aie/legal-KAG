from kag.builder.prompt.util import load_SPO_data
from kag.interface import PromptABC


@PromptABC.register("knowledge_unit_triple")
class OpenIEKnowledgeUnitTriplePrompt(PromptABC):
    template_en = """You are an expert specializing in knowledge graph relation extraction. Please refer to the given entity list to extract potential relations between any entities from the provided text, and list them in quadruple format.
If no relations are found, there is no need to list anything.
Please respond in JSON list format, where:

The overall structure is a list of quadruples and each quadruple is also a list. The output format is as follows:
[
    [subject entity, predicate, object entity, specific condiction],
    []
]

Please note the following requirements:
- The subject entity and object entity must either come from the provided entity_list or be meaningful noun phrases or proper nouns.
- Strictly prohibit object entities from containing meaningless terms: numeric values ("18 people"), dates ("December 1959"), pronouns ("there"), or ambiguous nouns ("current site").
- Predicates are typically semantic gerunds, verbs, or phrases that indicate actions, behaviors, or the connections between entities. The representation of predicates is directional, so it's advisable to avoid using prepositions such as "is" or "by." For instance, ["Zhi Xin Fund", "partner", "Liang Xiaodong"] is better than ["Liang Xiaodong", "acts as partner", "Zhi Xin Fund"].
- Specific constraints denote validity conditions (e.g., time, location). Use commas for multiple constraints. Leave empty if none exist.
- Each quadruplet must contain exactly four elements, separated by commas.

### Example:
input:SolarTech Innovations, a renewable energy startup headquartered in Berlin, unveiled its latest product 'EcoGrid Battery' during the annual Clean Energy Summit in June 2023. The advanced energy storage system was co-developed with OceanWave Labs, utilizing their marine-based cooling technology. CEO Dr. Helena Weiss confirmed the product will be distributed through GreenHub Stores across Europe starting Q1 2024. Technical specifications reveal the battery integrates patented 'NanoCool' modules, a breakthrough first presented at last year's Berlin Tech Expo. Environmental analysts predict this collaboration could reduce urban carbon emissions by 40% within five years.
entity_list: [
  ("SolarTech Innovations", "Organization"),
  ("EcoGrid Battery", "Technology"),
  ("OceanWave Labs", "Organization"),
  ("Dr. Helena Weiss", "Person"),
  ("NanoCool modules", "Technology"),
  ("Clean Energy Summit", "Event"),
  ("GreenHub Stores", "Organization")
]
output: [
  ["SolarTech Innovations", "unveiling", "EcoGrid Battery", "June 2023, Clean Energy Summit"],
  ["SolarTech Innovations", "co-developing", "OceanWave Labs", ""],
  ["EcoGrid Battery", "integrating", "NanoCool modules", ""],
  ["Dr. Helena Weiss", "announcing distribution", "GreenHub Stores", "Q1 2024"],
  ["OceanWave Labs", "providing", "marine-based cooling technology", ""]
]
### Input:
input: $input
entity_list: entity_list
"""

    @property
    def template_variables(self) -> list[str]:
        return ["entity_list", "input"]

    def parse_response(self, response: str, **kwargs):
        standardized_triples = load_SPO_data(response)
        return standardized_triples
