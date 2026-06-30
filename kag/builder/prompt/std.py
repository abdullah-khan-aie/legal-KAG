import json

from kag.interface import PromptABC


@PromptABC.register("default_std")
class OpenIEEntitystandardizationdPrompt(PromptABC):
    template_en = """
{
    "instruction": "The `input` field contains a user provided context. The `named_entities` field contains extracted named entities from the context, which may be unclear abbreviations, aliases, or slang. To eliminate ambiguity, please attempt to provide the official names of these entities based on the context and your own knowledge. Note that entities with the same meaning can only have ONE official name. Please respond in the format of a single JSONArray string without any explanation, as shown in the `output` field of the provided example.",
    "example": {
        "input": "American History.When did the political party that favored harsh punishment of southern states after the Civil War, gain control of the House? Republicans regained control of the chamber they had lost in the 2006 midterm elections.",
        "named_entities": [
            {"name": "American", "category": "GeographicLocation"},
            {"name": "political party", "category": "Organization"},
            {"name": "southern states", "category": "GeographicLocation"},
            {"name": "Civil War", "category": "Keyword"},
            {"name": "House", "category": "Organization"},
            {"name": "Republicans", "category": "Organization"},
            {"name": "chamber", "category": "Organization"},
            {"name": "2006 midterm elections", "category": "Date"}
        ],
        "output": [
            {
                "name": "American",
                "category": "GeographicLocation",
                "official_name": "United States of America"
            },
            {
                "name": "political party",
                "category": "Organization",
                "official_name": "Radical Republicans"
            },
            {
                "name": "southern states",
                "category": "GeographicLocation",
                "official_name": "Confederacy"
            },
            {
                "name": "Civil War",
                "category": "Keyword",
                "official_name": "American Civil War"
            },
            {
                "name": "House",
                "category": "Organization",
                "official_name": "United States House of Representatives"
            },
            {
                "name": "Republicans",
                "category": "Organization",
                "official_name": "Republican Party"
            },
            {
                "name": "chamber",
                "category": "Organization",
                "official_name": "United States House of Representatives"
            },
            {
                "name": "midterm elections",
                "category": "Date",
                "official_name": "United States midterm elections"
            }
        ]
    },
    "input": "$input",
    "named_entities": $named_entities
}
    """

    @property
    def template_variables(self) -> list[str]:
        return ["input", "named_entities"]

    def parse_response(self, response: str, **kwargs):
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        if isinstance(rsp, dict) and "named_entities" in rsp:
            standardized_entity = rsp["named_entities"]
        else:
            standardized_entity = rsp
        entities_with_offical_name = set()
        merged = []
        entities = kwargs.get("named_entities", [])

        # The caller does not have a unified input data structure, so multiple structures are treated uniformly here
        if "entities" in entities:
            entities = entities["entities"]
        if isinstance(entities, dict):
            _entities = []
            for category in entities:
                _e = entities[category]
                if isinstance(_e, list):
                    for _e2 in _e:
                        _entities.append({"name": _e2, "category": category})
                elif isinstance(_e, str):
                    _entities.append({"name": _e, "category": category})
                else:
                    pass

        for entity in standardized_entity:
            merged.append(entity)
            entities_with_offical_name.add(entity["name"])
        # in case llm ignores some entities
        for entity in entities:
            # Ignore entities without a name attribute
            if "name" in entity and entity["name"] not in entities_with_offical_name:
                entity["official_name"] = entity["name"]
                merged.append(entity)
        return merged
