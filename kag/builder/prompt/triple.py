import json

from kag.interface import PromptABC


@PromptABC.register("default_triple")
class OpenIETriplePrompt(PromptABC):
    template_en = """
{
    "instruction": "You are an expert specializing in carrying out open information extraction (OpenIE). Please extract any possible relations (including subject, predicate, object) from the given text, and list them following the json format {\"triples\": [[\"subject\", \"predicate\",  \"object\"]]}. If there are none, do not list them..Pay attention to the following requirements:- Each triple should contain at least one, but preferably two, of the named entities in the entity_list.- Clearly resolve pronouns to their specific names to maintain clarity.",
    "entity_list": $entity_list,
    "input": "$input",
    "example": {
        "input": "The RezortThe Rezort is a 2015 British zombie horror film directed by Steve Barker and written by Paul Gerstenberger. It stars Dougray Scott, Jessica De Gouw and Martin McCann. After humanity wins a devastating war against zombies, the few remaining undead are kept on a secure island, where they are hunted for sport. When something goes wrong with the island's security, the guests must face the possibility of a new outbreak.",
        "entity_list": [
            {
                "name": "The Rezort",
                "category": "Works"
            },
            {
                "name": "2015",
                "category": "Others"
            },
            {
                "name": "British",
                "category": "GeographicLocation"
            },
            {
                "name": "Steve Barker",
                "category": "Person"
            },
            {
                "name": "Paul Gerstenberger",
                "category": "Person"
            },
            {
                "name": "Dougray Scott",
                "category": "Person"
            },
            {
                "name": "Jessica De Gouw",
                "category": "Person"
            },
            {
                "name": "Martin McCann",
                "category": "Person"
            },
            {
                "name": "zombies",
                "category": "Creature"
            },
            {
                "name": "zombie horror film",
                "category": "Concept"
            },
            {
                "name": "humanity",
                "category": "Concept"
            },
            {
                "name": "secure island",
                "category": "GeographicLocation"
            }
        ],
        "output": [
            [
                "The Rezort",
                "is",
                "zombie horror film"
            ],
            [
                "The Rezort",
                "publish at",
                "2015"
            ],
            [
                "The Rezort",
                "released",
                "British"
            ],
            [
                "The Rezort",
                "is directed by",
                "Steve Barker"
            ],
            [
                "The Rezort",
                "is written by",
                "Paul Gerstenberger"
            ],
            [
                "The Rezort",
                "stars",
                "Dougray Scott"
            ],
            [
                "The Rezort",
                "stars",
                "Jessica De Gouw"
            ],
            [
                "The Rezort",
                "stars",
                "Martin McCann"
            ],
            [
                "humanity",
                "wins",
                "a devastating war against zombies"
            ],
            [
                "the few remaining undead",
                "are kept on",
                "a secure island"
            ],
            [
                "they",
                "are hunted for",
                "sport"
            ],
            [
                "something",
                "goes wrong with",
                "the island's security"
            ],
            [
                "the guests",
                "must face",
                "the possibility of a new outbreak"
            ]
        ]
    }
}    
    """

    @property
    def template_variables(self) -> list[str]:
        return ["entity_list", "input"]

    def parse_response(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        if isinstance(rsp, dict) and "triples" in rsp:
            triples = rsp["triples"]
        else:
            triples = rsp

        standardized_triples = []
        for triple in triples:
            if isinstance(triple, list):
                standardized_triples.append(triple)
            elif isinstance(triple, dict):
                s = triple.get("subject")
                p = triple.get("predicate")
                o = triple.get("object")
                if s and p and o:
                    standardized_triples.append([s, p, o])

        return standardized_triples
