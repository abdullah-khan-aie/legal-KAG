import json
import re

from kag.builder.prompt.util import load_knowIE_data
from kag.interface import PromptABC


@PromptABC.register("knowledge_unit")
class KnowledgeUnitPrompt(PromptABC):
    template_en = """You are an assistant for document analysis and knowledge unit extraction. Please extract substantial discussions, arguments, or analyses from the input document chunks. Ensure that the extracted knowledge units are strictly related to the document's theme and are the core content that the author directly introduces, analyzes, or argues within the chunk.

### Extraction Requirements:
- Identify the core argument in the chunk and extract content that makes a creative contribution to the document's theme.
- If the chunk contains numerous citations or mentions, only extract significant knowledge units involved when further analyzing, expanding, arguing, or applying these contents. Exclude auxiliary knowledge units or background information that are merely cited or mentioned.
- The names of knowledge units should be described using concise and clear language, fully reflecting the core theme of the knowledge unit.
- A knowledge unit is a complete and coherent whole, with clear arguments. Multiple knowledge units may be extracted from a chunk, but if further division would fail to preserve the context, argumentation process, etc., of the knowledge unit, the entire chunk should not be subdivided further. The content description of knowledge units should be clear and organized, avoiding superfluous or repetitive explanations.

### Knowledge Types
- Declarative Knowledge: Narratives explaining concepts, terms, theorems, clauses, etc., answering 'what' questions, including concept definitions, term explanations, arguments, formulas, legal provisions, etc.
- Case Knowledge: Demonstrating and explaining abstract concepts and theories through specific situations or examples, including judicial precedents, math problems, medical cases, etc., usually treated as a single complete knowledge unit.
- Factual Knowledge: Describing the state, attributes, characteristics, or background information of things, including historical events, news information, entity introductions, etc.
- Procedural Knowledge: Knowledge about how to perform tasks or operations, including program code, algorithms, operational steps, experimental processes, equation sets for problem-solving, etc.
- Analytical Knowledge: Knowledge derived through logical analysis, calculations, induction, deduction, etc., to support views or conclusions, answering 'why' and 'how to derive conclusions' questions.


### Output Format:
{
  "knowledge unit 1 Name":
  { 
    "Content": "A text excerpt extracted or summarized from the chunk, must include critical information that unambiguously explains the knowledge unit's content and subject.",
    "Knowledge Type": "Declarative Knowledge / Case Knowledge / Factual Knowledge / Procedural Knowledge / Analytical Knowledge",
    "Structural Content": "Structured content associated with the knowledge unit, such as charts, formulas, code, rules, first-order logic representation, equation sets, data structure definitions, etc.",
    "Domain Ontology": "The hierarchical classification system of disciplines or professional fields to which knowledge units belong. It is important to note that the terms at each level are general concepts rather than specific instances (remove individual person, organizations, etc. for the ontology).",
    "Core Entities": "Keywords that represent the subject or characteristics of the knowledge unit, ensuring that each term is semantically complete and reflects the knowledge unit's distinctiveness in searches relative to other content, and the valid type of each core entity is listed in the `Entity Types`",
    "Related Query": "The three most relevant query questions based on the knowledge unit's subject and content",
    "Extended Knowledge Points": "Other highly related but divergent knowledge points not included in the current knowledge point"
 },
  "knowledge unit 2 Name": {},
  ……
}

### Example:
input:"No Mediocre" is a song by American rapper T.I., released on June 17, 2014, through Grand Hustle and Columbia Records, as the lead single from his ninth studio album "Paperwork" (2014). The song, produced by DJ Mustard, features a guest appearance from Grand Hustle protégé, Australian rapper Iggy Azalea.
output:
{
  "No Mediocre Song Details":{
    "Content": "\"No Mediocre\" is a song by American rapper T.I., released as the lead single from his ninth studio album \"Paperwork\" (2014). The track, produced by DJ Mustard, includes a guest appearance by Australian rapper Iggy Azalea. It peaked at number 69 on the US Billboard Hot 100 and was met with positive reviews for its production and Azalea's contribution.",
    "Knowledge Type": "Factual Knowledge",
    "Structural Content": "",
    "Domain Ontology": "Music -> Hip Hop -> T.I. Discography -> No Mediocre",
    "Core Entities": {"T.I.": "Person", "No Mediocre" : "Culture and Entertainment", "Paperwork" : "Culture and Entertainment", "DJ Mustard" : "Person", "Iggy Azalea": "Person", "US Billboard Hot 100": "Culture and Entertainment" },
    "Related Query": ["What is the lead single from T.I.'s ninth studio album?", "Who produced the song 'No Mediocre'?", "What was the peak position of 'No Mediocre' on the US Billboard Hot 100?"],
    "Extended Knowledge Points": ["T.I.'s discography", "DJ Mustard's production work", "Iggy Azalea's collaborations", "US Billboard Hot 100 chart", "Critical reception of 'No Mediocre'", "Soundtrack for 'Think Like a Man Too'"]
  }
}
### Input:
input: $input
"""

    template_zh = """You are an assistant for document analysis and knowledge unit extraction. From the input document chunk, please extract knowledge units that give a substantive description and introduction of the document's background knowledge, people involved, time, and place, or that substantively discuss, argue, or analyze relevant information in the content.
Please ensure that the extracted knowledge units are strictly related to the document's theme and are the core content that the author directly introduces, analyzes, or argues within the chunk.
If the subject described by a knowledge unit cannot be confirmed but the document's core entity information is provided in the input, please refer to it.

### Extraction Requirements:
1. Identify the core argument object in the chunk, and extract content that makes a creative contribution to the document's theme.
2. If the chunk contains many citations or mentions, only extract the important knowledge units involved when further analyzing, expanding, arguing, or applying these contents. Do not include auxiliary knowledge units or background content that are merely cited or mentioned.
3. The names of knowledge units should be described using concise and clear language, fully reflecting the core theme of the knowledge unit.
4. A knowledge unit is a complete and coherent whole with clear argumentation. A chunk may yield multiple knowledge units: when the same theme or subject is discussed in parallel from multiple aspects, split it into multiple knowledge units; when further division would fail to fully preserve the cause-and-effect, argumentation process, etc. of a knowledge unit, treat the entire chunk as one knowledge unit without further subdivision.
5. The content description of knowledge units should be clear and organized, avoiding superfluous or repetitive explanations.

### Knowledge Types
Declarative Knowledge: Narratives explaining a domain's concepts, terms, theorems, clauses, etc., answering 'what' questions, including concept definitions, term explanations, arguments, formulas, legal provisions, etc.
Case Knowledge: Demonstrating and explaining abstract concepts and theories through specific situations or examples, including judicial precedents, math problems, medical cases, etc.; usually a single case is treated as one complete knowledge unit.
Factual Knowledge: Describing the state, attributes, characteristics, or background information of things, including historical events, news information, entity introductions, etc.
Procedural Knowledge: Knowledge about how to perform tasks or operations, including program code, algorithms, operational steps, experimental processes, equation sets for problem-solving, etc.
Analytical Knowledge: Knowledge derived through logical analysis, calculation, induction, deduction, etc., to support views or conclusions; it answers 'why' and 'how to derive conclusions' questions.

### Output Format:
{
  "knowledge unit 1 Name":
  {
    "Content": "A text excerpt extracted or summarized from the chunk, which must include key information that unambiguously explains the knowledge unit's content and subject.",
    "Knowledge Type": "Declarative Knowledge / Case Knowledge / Factual Knowledge / Procedural Knowledge / Analytical Knowledge",
    "Structured Content": "Structured content associated with the knowledge unit, such as charts, formulas, code, rules, first-order logic representation, equation sets, data structure definitions, etc.",
    "Domain Ontology": "The hierarchical (hypernym/hyponym) classification system of the discipline or professional field to which the knowledge unit belongs",
    "Core Entities": "Keywords that reflect the subject or characteristics of the knowledge unit; note that each entity term must be semantically complete and reflect the knowledge unit's distinctiveness in retrieval relative to other content",
    "Related Query": "The query questions that can be answered based on the knowledge unit's subject and content",
    "Extended Knowledge Points": "Other highly related but divergent knowledge not included in the current knowledge unit"
  },
  "knowledge unit 2 Name": {},
  ……
}

### Example:
input:
From January to December 2019, national power generation was 7,142.2 billion kWh, up 3.5% year-on-year, with the growth rate down 3.3 pct from the same period of the previous year. By generation method:\n* Thermal power generation was 5,165.4 billion kWh, up 1.9% year-on-year, with the growth rate down 4.1 pct year-on-year.\n◆ Hydropower generation was 1,153.4 billion kWh, up 4.8% year-on-year, with the growth rate up 0.7 pct year-on-year.\n◆ Nuclear power generation was 348.4 billion kWh, up 18.3% year-on-year, with the growth rate down 0.4 pct year-on-year.\n◆ Wind power generation was 357.7 billion kWh, up 7.0% year-on-year, with the growth rate down 9.6 pct year-on-year.\n◆ Solar power generation was 117.2 billion kWh, up 13.3% year-on-year, with the growth rate down 6.3 pct year-on-year.\nFigure 44: Cumulative year-on-year growth rate of generation by method (%)\nSource: National Bureau of Statistics, Shengang Securities Research Institute\nFigure 45: Share of monthly generation by method (%)\nSource: National Bureau of Statistics, Shengang Securities Research Institute
output: {
  "2019 National Thermal Power Generation": {
    "Content": "In 2019, national thermal power generation was 5,165.4 billion kWh, up 1.9% year-on-year, with the growth rate down 4.1 percentage points year-on-year",
    "Knowledge Type": "Factual Knowledge",
    "Structured Content": "",
    "Domain Ontology": "Energy Statistics -> Power Production -> Generation Method Classification -> Thermal Power",
    "Core Entities": "thermal power generation, year-on-year growth rate, 2019",
    "Related Query": ["What was the national thermal power generation in 2019?", "Trend of thermal power generation growth rate"],
    "Extended Knowledge Points": ["2018 national thermal power generation", "thermal power generation method"]
  },
  "2019 National Hydropower Generation": {
    "Content": "In 2019, national hydropower generation was 1,153.4 billion kWh, up 4.8% year-on-year, with the growth rate up 0.7 percentage points year-on-year",
    "Knowledge Type": "Factual Knowledge",
    "Structured Content": "",
    "Domain Ontology": "Energy Statistics -> Power Production -> Generation Method Classification -> Hydropower",
    "Core Entities": "hydropower generation, growth rate increase, 2019",
    "Related Query": ["Hydropower generation growth in 2019"],
    "Extended Knowledge Points": ["2018 national hydropower generation", "comparison of hydropower and thermal power growth", "clean energy development data"]
  },
  "2019 National Nuclear Power Generation": {
    "Content": "In 2019, national nuclear power generation was 348.4 billion kWh, up 18.3% year-on-year, with the growth rate down 0.4 percentage points year-on-year",
    "Knowledge Type": "Factual Knowledge",
    "Structured Content": "",
    "Domain Ontology": "Energy Statistics -> Power Production -> Generation Method Classification -> Nuclear Power",
    "Core Entities": "nuclear power generation, high growth rate, 2019",
    "Related Query": ["2019 nuclear power generation growth-rate data"],
    "Extended Knowledge Points": ["2018 national nuclear power generation", "analysis of the current state of clean energy development", "reasons for nuclear power generation growth"]
  },
  "2019 National Wind Power Generation": {
    "Content": "In 2019, national wind power generation was 357.7 billion kWh, up 7.0% year-on-year, with the growth rate down 9.6 percentage points year-on-year",
    "Knowledge Type": "Factual Knowledge",
    "Structured Content": "",
    "Domain Ontology": "Energy Statistics -> Power Production -> Generation Method Classification -> Wind Power",
    "Core Entities": "wind power generation, growth rate decline, 2019",
    "Related Query": ["Trend of wind power generation"],
    "Extended Knowledge Points": ["2018 national wind power generation", "comparison of wind and photovoltaic growth", "renewable energy development assessment"]
  },
  "2019 National Solar Power Generation": {
    "Content": "In 2019, national solar power generation was 117.2 billion kWh, up 13.3% year-on-year, with the growth rate down 6.3 percentage points year-on-year",
    "Knowledge Type": "Factual Knowledge",
    "Structured Content": "",
    "Domain Ontology": "Energy Statistics -> Power Production -> Generation Method Classification -> Solar Power",
    "Core Entities": "solar power generation, growth rate change, 2019",
    "Related Query": ["2019 national solar power generation growth data"],
    "Extended Knowledge Points": ["2018 national thermal power generation", "definition of solar energy", "comparison of solar and wind energy development", "2019 total renewable energy generation"]
  },
  "2019 National Total Power Generation and Structure": {
    "Content": "In 2019, national total power generation was 7,142.2 billion kWh, up 3.5% year-on-year. Of this, thermal power accounted for 72.3%, hydropower 16.15%, nuclear power 4.88%, wind power 5.01%, and solar power 1.64%",
    "Knowledge Type": "Factual Knowledge",
    "Structured Content": "",
    "Domain Ontology": "Energy Statistics -> Power Production -> Overall Generation Data Analysis",
    "Core Entities": "total generation structure, year-on-year growth, 2019",
    "Related Query": ["2019 power generation structure distribution", "share of each generation type in 2019 national total generation"],
    "Extended Knowledge Points": ["2018 national total generation and structure", "generation methods"]
  }
}
### Input:
input: $input
"""

    @property
    def template_variables(self) -> list[str]:
        return ["input", "named_entities"]

    def modify_knowledge_unit(self, text, lang="zh"):
        # define the regex pattern
        if lang == "zh":
            pattern = r'"knowledge unit \d+ Name"\s*:\s*"([^"]+)"\s*,'
        else:
            pattern = r'"knowledge unit \d+ Name"\s*:\s*"([^"]+)",'
        # use re.sub to perform the replacement
        # print(pattern)
        modified_text = re.sub(pattern, r'"\1":', text)

        # print("modified_text:",modified_text)
        return modified_text

    def process_data(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        return rsp

    def process_en(self, response: dict, **kwargs):
        """ "No Mediocre Song Details":{
          "Content": "\"No Mediocre\" is a song by American rapper T.I., released as the lead single from his ninth studio album \"Paperwork\" (2014). The track, produced by DJ Mustard, includes a guest appearance by Australian rapper Iggy Azalea. It peaked at number 69 on the US Billboard Hot 100 and was met with positive reviews for its production and Azalea's contribution.",
          "Knowledge Type": "Factual Knowledge",
          "Structural Content": "",
          "Domain Ontology": "Music -> Hip Hop -> T.I. Discography -> No Mediocre",
          "Core Entities": "T.I., No Mediocre, Paperwork, DJ Mustard, Iggy Azalea, US Billboard Hot 100",
          "Related Query": ["What is the lead single from T.I.'s ninth studio album?", "Who produced the song 'No Mediocre'?", "What was the peak position of 'No Mediocre' on the US Billboard Hot 100?"],
          "Extended Knowledge Points": ["T.I.'s discography", "DJ Mustard's production work", "Iggy Azalea's collaborations", "US Billboard Hot 100 chart", "Critical reception of 'No Mediocre'", "Soundtrack for 'Think Like a Man Too'"]
        }"""
        ret = {}
        if "Content" in response.keys():
            ret["content"] = response["Content"]
        if "Knowledge Type" in response.keys():
            ret["knowledgetype"] = response["Knowledge Type"]
        if "Domain Ontology" in response.keys():
            ret["ontology"] = response["Domain Ontology"]
        if "Core Entities" in response.keys():
            ret["core_entities"] = response["Core Entities"]
        if "Related Query" in response.keys():
            ret["relatedQuery"] = response["Related Query"]
        if "Extended Knowledge Points" in response.keys():
            ret["extendedKnowledge"] = response["Extended Knowledge Points"]
        return ret

    def process_zh(self, response: dict, **kwargs):
        """ "2019 National Total Power Generation and Structure": {
          "Content": "In 2019, national total power generation was 7,142.2 billion kWh, up 3.5% year-on-year. Of this, thermal power accounted for 72.3%, hydropower 16.15%, nuclear power 4.88%, wind power 5.01%, and solar power 1.64%",
          "Knowledge Type": "Factual Knowledge",
          "Structured Content": "",
          "Domain Ontology": "Energy Statistics -> Power Production -> Overall Generation Data Analysis",
          "Core Entities": "total generation structure, year-on-year growth, 2019",
          "Related Query": ["2019 power generation structure distribution", "share of each generation type in 2019 national total generation"],
          "Extended Knowledge Points": ["2018 national total generation and structure", "generation methods"]
        }"""
        ret = {}
        if "Content" in response.keys():
            ret["content"] = response["Content"]
        if "Knowledge Type" in response.keys():
            ret["knowledgetype"] = response["Knowledge Type"]
        if "Domain Ontology" in response.keys():
            ret["ontology"] = response["Domain Ontology"]
        if "Core Entities" in response.keys():
            ret["core_entities"] = response["Core Entities"]
        if "Related Query" in response.keys():
            ret["relatedQuery"] = response["Related Query"]
        if "Extended Knowledge Points" in response.keys():
            ret["extendedKnowledge"] = response["Extended Knowledge Points"]
        return ret

    def parse_response(self, response: str, **kwargs):
        # response = self.modify_knowledge_unit(response,lang = self.language)
        # rsp = self.process_data(response)
        rsp = load_knowIE_data(response)
        ret = {}
        for k, v in rsp.items():
            ret[k] = (
                self.process_en(v, **kwargs)
                if self.language == "en"
                else self.process_zh(v, **kwargs)
            )
        return ret
