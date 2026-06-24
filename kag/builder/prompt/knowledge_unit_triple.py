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

    template_zh = """You are an expert specializing in knowledge graph relation extraction. Please refer to the given entity list to extract any possible relations between entities from the given text, and list them in the format of a list of quadruples. If no relations are found, there is no need to list anything.
Please respond in JSON list format; the whole is a list, where each quadruple is also a list, in the format:
[
  [subject entity, predicate, object entity, specific constraint],
  []
]

Please note the following requirements:
1. The subject entity and object entity must either be entities involved in the entity list given below, or be meaningful entity nouns or proper nouns; modifiers may be added appropriately to make the entity description more accurate, e.g., "free parking service".
2. It is strictly prohibited for object entities to use meaningless terms such as numeric values ("18 people"), dates ("December 1959"), pronouns ("there"), or ambiguous nouns ("current site").
3. Predicates are mostly semantically clear gerunds, verbs, or other relational words or phrases that indicate actions, behaviors, or the connections and relations between entities. Predicates are directional, so choose the best direction and avoid prepositions such as "is" or "by"; for example, ["Zhi Xin Capital", "partner", "Liang Xiaodong"] is better than ["Liang Xiaodong", "serves as partner of", "Zhi Xin Capital"].
4. A specific constraint is a validity condition that determines when the "subject-predicate-object" sentence holds, such as a specific time of occurrence or a specific location; use commas to list multiple constraints. If no specific condition exists, leave it as an empty string.
5. Strictly ensure that each quadruple contains exactly four elements, separated by commas.

### Example
input: Title: CPC Dangyang Municipal Party School: a school within Dangyang City (Society/School)
Content: #CPC Dangyang Municipal Party School: a school within Dangyang City\nThe CPC Dangyang Municipal Party School and the Dangyang Municipal Administrative School are located at No. 129 Huancheng West Road, Dangyang City; they are a division-level public institution directly under the municipal Party committee and municipal government.\nChinese name: CPC Dangyang Municipal Party School. Founded: December 1959. Current principal: Shen Jianhua. Region: Dangyang City.\n##Development History\nThe CPC Dangyang Municipal Party School was founded in December 1959 and was suspended in 1960. It resumed in 1972, with its site at the former Niangniang Temple of the Xiongfeng Brigade in Yuyang Town. In February 1974, it moved to Guandang (the former Navy May Seventh Cadre School). In February 1975, following the instructions of the county Party committee, the Dangyang County May Seventh Cadre School was added. In August 1978, the May Seventh Cadre School was ordered to be abolished. In 1984, to implement the 'Decision of the CPC Central Committee on Standardizing Party School Education', it moved from Guandang to its current site. In April 1985, it was approved by relevant provincial departments as a county-level Party school under the secondary-vocational system. In May 1994, it was approved by the municipal Party committee and government to also run an administrative school, mainly responsible for training national civil servants. In October 1998, it was approved by the provincial Party school and the Yichang Municipal Party school to establish a correspondence station for academic education, mainly responsible for academic training of in-service cadres.\n##Faculty\nThe CPC Dangyang Municipal Party School and the Dangyang Municipal Administrative School currently have 18 staff members (on the payroll), including 12 national civil servants, 5 professional and technical personnel, and 1 logistics worker.\n##Internal Departments\nThe CPC Dangyang Municipal Party School and the Dangyang Municipal Administrative School have 4 departments: the Office, the Organization and Teaching Section, the Social Education Section, and the General Affairs Section; under the school committee there are 2 Party branches: the organ Party branch and the retiree Party branch.\n##Teaching Facilities\nThe school currently has 4 standardized classrooms (50 seats each), 1 tiered classroom (430 seats), 1 large classroom (100 seats), 1 multimedia classroom (50 seats), and 1 student dormitory with 150 beds. It trains about 500 cadres year-round.\nThe CPC Dangyang Municipal Party School and the Dangyang Municipal Administrative School cover 54 mu with a building area of 9,800 square meters. The campus greening rate and road hardening rate both reach 100%; it has repeatedly been rated a Dangyang City 'Civilized Unit' and 'Garden-style School', an 'Advanced Unit' in the Yichang Party school system, and a 'Qualified School' meeting the 'Ninth Five-Year' assessment standards of the provincial Party school system.\n##Leadership Team\nMember of the Dangyang Municipal Party Standing Committee, Head of the Organization Department, and Principal of the Municipal Party School: Meng Li\nParty Committee Secretary and Executive Vice Principal: Shen Jianhua\nParty Committee Member and Vice Principal: Wan Zhe\nParty Committee Member and Vice Principal: Lu Jianzhi\nParty Committee Member and Trade Union Chairperson: Xu Haifeng.
entity_list: [
    ("CPC Dangyang Municipal Party School", "Organization"),
    ("Dangyang Municipal Administrative School", "Organization"),
    ("Shen Jianhua", "Person"),
    ("Meng Li", "Person"),
    ("Wan Zhe", "Person"),
    ("Lu Jianzhi", "Person"),
    ("Xu Haifeng", "Person"),
    ("Dangyang City", "Geographic Location"),
    ("Niangniang Temple of the Xiongfeng Brigade in Yuyang Town", "Geographic Location"),
    ("Guandang", "Geographic Location"),
    ("Dangyang County May Seventh Cadre School", "Organization")
]
output: [
    ["CPC Dangyang Municipal Party School", "located at", "No. 129 Huancheng West Road, Dangyang City", ""],
    ["CPC Dangyang Municipal Party School", "current principal", "Shen Jianhua", ""],
    ["CPC Dangyang Municipal Party School", "region", "Dangyang City", ""],
    ["CPC Dangyang Municipal Party School", "founding time", "December 1959", ""],
    ["CPC Dangyang Municipal Party School", "suspension time", "1960", ""],
    ["CPC Dangyang Municipal Party School", "resumption time", "1972", ""],
    ["CPC Dangyang Municipal Party School", "site located at", "Niangniang Temple of the Xiongfeng Brigade in Yuyang Town", "when resumed in 1972"],
    ["CPC Dangyang Municipal Party School", "moved to", "Guandang", "February 1974"],
    ["CPC Dangyang Municipal Party School", "added", "Dangyang County May Seventh Cadre School", "February 1975"],
    ["CPC Dangyang Municipal Party School", "also runs", "Dangyang Municipal Administrative School", "May 1994"],
    ["CPC Dangyang Municipal Party School", "established", "academic education correspondence station", "October 1998"],
    ["CPC Dangyang Municipal Party School", "internal department", "Office", ""],
    ["CPC Dangyang Municipal Party School", "internal department", "Organization and Teaching Section", ""],
    ["CPC Dangyang Municipal Party School", "internal department", "Social Education Section", ""],
    ["CPC Dangyang Municipal Party School", "internal department", "General Affairs Section", ""],
    ["CPC Dangyang Municipal Party School", "subordinate branch", "organ Party branch", ""],
    ["CPC Dangyang Municipal Party School", "subordinate branch", "retiree Party branch", ""],
    ["CPC Dangyang Municipal Party School", "rated as", "Dangyang City Civilized Unit", ""],
    ["CPC Dangyang Municipal Party School", "rated as", "Garden-style School", ""],
    ["CPC Dangyang Municipal Party School", "rated as", "Advanced Unit in the Yichang Party school system", ""],
    ["CPC Dangyang Municipal Party School", "rated as", "Qualified School meeting the Ninth Five-Year assessment standards of the provincial Party school system", ""],
    ["Dangyang Municipal Administrative School", "located at", "No. 129 Huancheng West Road, Dangyang City", ""],
    ["Dangyang Municipal Administrative School", "mainly responsible for", "training of national civil servants", ""],
    ["Meng Li", "serves as", "member of the Dangyang Municipal Party Standing Committee", ""],
    ["Meng Li", "serves as", "Head of the Organization Department", ""],
    ["Meng Li", "serves as", "Principal of the CPC Dangyang Municipal Party School", ""],
    ["Shen Jianhua", "serves as", "Party Committee Secretary of the CPC Dangyang Municipal Party School", ""],
    ["Shen Jianhua", "serves as", "Executive Vice Principal of the CPC Dangyang Municipal Party School", ""],
    ["Wan Zhe", "serves as", "Party Committee Member of the CPC Dangyang Municipal Party School", ""],
    ["Wan Zhe", "serves as", "Vice Principal of the CPC Dangyang Municipal Party School", ""],
    ["Lu Jianzhi", "serves as", "Party Committee Member of the CPC Dangyang Municipal Party School", ""],
    ["Xu Haifeng", "serves as", "Party Committee Member of the CPC Dangyang Municipal Party School", ""],
    ["Xu Haifeng", "serves as", "Trade Union Chairperson of the CPC Dangyang Municipal Party School", ""],
    ["Dangyang County May Seventh Cadre School", "abolished from", "CPC Dangyang Municipal Party School", "August 1978"]
]
### Input:
input:$input
entity_list:$entity_list
"""

    @property
    def template_variables(self) -> list[str]:
        return ["entity_list", "input"]

    def parse_response(self, response: str, **kwargs):
        standardized_triples = load_SPO_data(response)
        return standardized_triples
