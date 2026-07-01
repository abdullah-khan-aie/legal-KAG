import copy
import json
import logging
from typing import ClassVar

from kag.interface import PromptABC
from kag.schema.client import (
    OTHER_TYPE,
    ConstraintTypeEnum,
    SchemaClient,
    SpgTypeEnum,
    SPGTypeName,
)

SPGRecord = dict

logger = logging.getLogger(__name__)


class SPGPrompt(PromptABC):
    """Base class for generating SPG schema-based entity/event extraction prompts.

    Attributes:
        ignored_types: SPG types to exclude from the prompt schema.
        ignored_properties: Properties to exclude from the prompt schema.
        default_properties: Properties applied to every SPG type by default.
        ignored_relations: Relations to exclude from the prompt schema.
    """

    ignored_types: ClassVar[list[str]] = ["Chunk"]
    ignored_properties: ClassVar[list[str]] = [
        "id",
        "stdId",
        "desc",
        "description",
        "eventTime",
    ]
    default_properties: ClassVar[dict[str, str]] = {
        "name": "Text",
    }

    ignored_relations: ClassVar[list[str]] = ["isA"]

    def __init__(
        self,
        spg_type_names: list[SPGTypeName] | None = None,
        language: str = "",
        **kwargs,
    ):
        """Initialize the prompt, loading the schema for the given SPG type names.

        Args:
            spg_type_names: SPG type names to restrict the prompt schema to; empty
                uses the full schema.
            language: Language for the prompt.
        """
        super().__init__(**kwargs)
        self.schema = SchemaClient(schema_path=kwargs.get("schema_path")).load()
        self.spg_type_names = spg_type_names or []
        if not spg_type_names:
            self.spg_types = self.schema
        else:
            self.spg_types = {k: v for k, v in self.schema.items() if k in spg_type_names}
        self.create_prompt_schema()

    @property
    def template_variables(self) -> list[str]:
        """Return the template variables used in the prompt."""
        return ["schema", "input"]

    @staticmethod
    def get_accept_types():
        """Return the SPG type enums this prompt extracts."""
        return [
            SpgTypeEnum.Entity,
            SpgTypeEnum.Concept,
            SpgTypeEnum.Event,
        ]

    def build_prompt(self, variables: dict[str, str]) -> str:
        """Build the prompt text from the given input variables and prompt schema.

        Args:
            variables: Input variables to render into the prompt.
        """
        return super().build_prompt(
            {
                "schema": copy.deepcopy(self.prompt_schema),
                "input": variables.get("input"),
            }
        )

    @staticmethod
    def process_property_name(name: str):
        """Strip a parenthesized description from a property name.

        Args:
            name: A property name, possibly with a parenthesized description.

        Example:
            >>> name = 'authors(authors of work, such as director, actor, lyricist, composer and singer)'
            >>> process_property_name(input_properties)
            'authors'
        """

        return name.split("(")[0]

    def process_property_names(self, properties: dict):
        """Strip parenthesized descriptions from all property names, recursing into nested dicts.

        Args:
            properties: Properties keyed by name (possibly with parenthesized
                descriptions); values may be plain values or nested dicts.

        Returns:
            A new dict with the same structure but cleaned property names.

        Example:
            >>> input_properties = {
            ...     "authors(authors of work, such as director, actor, lyricist, composer and singer)": "John Doe"
            ... }
            >>> process_property_names(input_properties)
            {'authors': 'John Doe'}
        """
        output = {}
        for k, v in properties.items():
            k = self.process_property_name(k)
            if isinstance(v, dict):
                output[k] = self.process_property_names(v)
            else:
                output[k] = v
        return output

    def parse_response(self, response: str, **kwargs) -> list[SPGRecord]:
        """Parse the model response into a list of SPG records.

        Args:
            response: The raw model response (JSON string or already-parsed object).
        """
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        outputs = []
        for item in rsp:
            if "category" not in item or item["category"] not in self.schema:
                continue
            properties = item.get("properties", {})
            if "name" not in properties:
                continue
            output = {}
            output["category"] = item["category"]
            output["name"] = properties.pop("name")
            output["properties"] = self.process_property_names(properties)
            outputs.append(output)
        return outputs

    def create_prompt_schema(self):
        """Build the prompt schema (types, properties, relations) from the project schema."""
        prompt_schema = []
        accept_types = self.get_accept_types()
        for type_name, spg_type in self.spg_types.items():
            if type_name in self.ignored_types:
                continue
            if spg_type.spg_type_enum not in accept_types:
                continue
            type_desc = spg_type.desc
            properties = copy.deepcopy(self.default_properties)
            for k, v in spg_type.properties.items():
                if k in self.ignored_properties or k in self.default_properties:
                    continue
                multi_value = ConstraintTypeEnum.MultiValue.value in v.constraint
                obj_type_name = v.object_type_name.split(".")[-1]
                if multi_value:
                    obj_type_name = f"List[{obj_type_name}]"
                if v.desc:
                    v_name = f"{v.name}({v.desc})"
                else:
                    v_name = v.name
                properties[v_name] = obj_type_name

            for k, v in spg_type.relations.items():
                if k in self.ignored_relations or k in self.default_properties:
                    continue
                if v.name in properties:
                    continue
                obj_type_name = v.object_type_name.split(".")[-1]
                if v.desc:
                    v_name = f"{v.name}({v.desc})"
                else:
                    v_name = v.name
                properties[v_name] = obj_type_name

            if type_desc:
                prompt_schema.append({f"{type_name}({type_desc})": {"properties": properties}})
            else:
                prompt_schema.append({type_name: {"properties": properties}})

        self.prompt_schema = prompt_schema


@PromptABC.register("spg_entity")
class SPGEntityPrompt(SPGPrompt):
    template_en: ClassVar[dict] = {
        "instruction": "As an expert in graph knowledge extraction, you need to extract all entities and their properties from the text in the input field based on a schema that defines entity types and their corresponding attributes. Attributes marked as List in the schema should return a list, and attributes not extracted should return null. Output the results in a standard JSON list format, where each element in the list is in the form of {category: properties}. You can refer to the example format provided in the example field. Note that the SemanticType of an entity attribute refers to a more specific and clearly defined type compared to the entity type itself, such as Professor or Actor for the Person type.",
        "example": [
            {
                "input": "Jay Chou, born on January 18, 1979, in New Taipei City, Taiwan Province, with ancestral roots in Yongchun County, Fujian Province, is a renowned male singer, musician, actor, director, and screenwriter in the realm of Chinese pop music. He graduated from Tamkang University. In 2000, he released his debut solo album, <Jay> [26]. In 2023, he was honored with three major awards at the inaugural Wave Music Awards for Best Production, Best Composition, and Best Music Video for his album The Greatest Work.",
                "output": [
                    {
                        "category": "Person",
                        "properties": {
                            "name": "Jay Chou",
                            "semanticType": "Musician",
                            "description": "renowned male singer, musician, actor, director, and screenwriter in the realm of Chinese pop music",
                        },
                    },
                    {
                        "category": "GeographicLocation",
                        "properties": {
                            "name": "New Taipei City, Taiwan Province",
                            "semanticType": "City",
                            "description": "Jay Chou's birthplace",
                        },
                    },
                    {
                        "category": "GeographicLocation",
                        "properties": {
                            "name": "Yongchun County, Fujian Province",
                            "semanticType": "County",
                            "description": "Jay Chou's ancestral roots",
                        },
                    },
                    {
                        "category": "Organization",
                        "properties": {
                            "name": "Tamkang University",
                            "semanticType": "University",
                            "description": "Jay Chou's alma mater",
                        },
                    },
                    {
                        "category": "Works",
                        "properties": {
                            "name": "Jay",
                            "semanticType": "Album",
                            "description": "Jay Chou's debut solo album",
                        },
                    },
                    {
                        "category": "Works",
                        "properties": {
                            "name": "The Greatest Work",
                            "semanticType": "Album",
                            "description": "Jay Chou's album for which he won multiple awards",
                        },
                    },
                ],
            }
        ],
    }

    @staticmethod
    def get_accept_types():
        return [
            SpgTypeEnum.Entity,
            SpgTypeEnum.Concept,
        ]


@PromptABC.register("spg_event")
class SPGEventPrompt(SPGPrompt):
    template_en: ClassVar[dict] = {
        "instruction": "As an expert in knowledge graph event extraction, you need to extract all events and their attributes from the text in the input field based on the defined event types and corresponding attribute schema. For attributes marked as List in the schema, return them as a list, and for attributes that cannot be extracted, return null. Output in the standard JSON list format, with each element in the list having the form {category: properties}. You can refer to the example format provided in the example field.",
        "example": {
            "input": "In 1986, Stephen Chow was transferred to the drama department of Television Broadcasts Limited (TVB). In the same year, he played the role of Pan Jiawei, a lovable, lively, and slightly shy character, in the episodic situational comedy <My Brother's Girlfriend.> This was his first time taking on a lead role in a sitcom. Later, he also had minor roles in TV series starring actors such as Anthony Wong and Aaron Kwok.",
            "output": [
                {
                    "category": "Event",
                    "properties": {
                        "name": "Stephen Chow was transferred to the drama department of TVB",
                        "abstract": "In 1986, Stephen Chow was transferred to the drama department of Television Broadcasts Limited (TVB).",
                        "subject": "Stephen Chow",
                        "time": "1986",
                        "location": "Television Broadcasts Limited (TVB)",
                        "participants": [],
                        "semanticType": "Transfer",
                    },
                },
                {
                    "category": "Event",
                    "properties": {
                        "name": "Stephen Chow played Pan Jiawei in My Brother's Girlfriend",
                        "abstract": "In 1986, Stephen Chow played the role of Pan Jiawei, a lovable, lively, and slightly shy character, in the episodic situational comedy <My Brother's Girlfriend.> This was his first time taking on a lead role in a sitcom.",
                        "subject": "Stephen Chow",
                        "time": "1986",
                        "location": None,
                        "participants": [],
                        "semanticType": "Performance",
                    },
                },
                {
                    "category": "Event",
                    "properties": {
                        "name": "Stephen Chow had minor roles in TV series",
                        "abstract": "Later, Stephen Chow also had minor roles in TV series starring actors such as Anthony Wong and Aaron Kwok.",
                        "subject": "Stephen Chow",
                        "time": None,
                        "location": None,
                        "participants": ["Anthony Wong", "Aaron Kwok"],
                        "semanticType": "Performance",
                    },
                },
            ],
        },
    }

    @staticmethod
    def get_accept_types():
        return [
            SpgTypeEnum.Event,
        ]


@PromptABC.register("spg_relation")
class SPGRelationPrompt(SPGPrompt):
    template_en: ClassVar[dict] = {
        "instruction": "You are an expert in Open Information Extraction (OpenIE). The schema defines the entity types you need to focus on, along with optional type explanations enclosed in parentheses. The entity_list is a set of entity lists. Please extract any possible [subject entity, subject entity class type, predicate, object entity, object entity type] quintuples from the text in the input field and list them in JSON list format. Please adhere strictly to the following requirements:1. At least one of the subject entity and object entity must appear in the entity_list.\n2. The subject and object entity types must be defined in the schema; otherwise, they are considered invalid.\n3.Resolve pronouns to their corresponding names explicitly to maintain clarity.",
        "example": {
            "input": "In 1986, Stephen Chow was transferred to the drama division of TVB; that same year, he played the cute, lively, and slightly shy Pan Jiawei in the situational drama 'My Brother's Girlfriend,' which was also his first time as the male lead in a situational drama; later, he also appeared as an extra in TV dramas starring Deric Wan, Roger Kwok, and others.",
            "entity_list": [
                {"name": "Stephen Chow", "category": "Person"},
                {"name": "TVB", "category": "Organization"},
                {"name": "My Brother's Girlfriend", "category": "Works"},
                {"name": "Pan Jiawei", "category": "Person"},
                {"name": "Deric Wan", "category": "Person"},
                {"name": "Roger Kwok", "category": "Person"},
            ],
            "output": [
                ["Stephen Chow", "Person", "was transferred to", "TVB", "Organization"],
                [
                    "Stephen Chow",
                    "Person",
                    "starred in",
                    "My Brother's Girlfriend",
                    "Works",
                ],
                ["Stephen Chow", "Person", "played", "Pan Jiawei", "Person"],
                ["Stephen Chow", "Person", "co-starred with", "Deric Wan", "Person"],
                ["Stephen Chow", "Person", "co-starred with", "Roger Kwok", "Person"],
                [
                    "Stephen Chow",
                    "Person",
                    "appeared as an extra in",
                    "TV dramas starring Deric Wan, Roger Kwok, and others",
                    "Works",
                ],
            ],
        },
    }

    @staticmethod
    def get_accept_types():
        """Return the SPG type enums this prompt extracts."""
        return [
            SpgTypeEnum.Entity,
            SpgTypeEnum.Concept,
        ]

    def build_prompt(self, variables: dict[str, str]) -> str:
        """Build the prompt text from the given input variables and prompt schema.

        Args:
            variables: Input variables to render into the prompt.
        """
        schema = []
        for item in self.prompt_schema:
            schema.extend(item.keys())
        return super().build_prompt(
            {
                "schema": schema,
                "input": variables.get("input"),
            }
        )

    def parse_response(self, response: str, **kwargs) -> list[SPGRecord]:
        """Parse the model response into a list of SPG records.

        Args:
            response: The raw model response (JSON string or already-parsed object).
        """
        rsp = response
        if isinstance(rsp, str):
            rsp = json.loads(rsp)
        if isinstance(rsp, dict) and "output" in rsp:
            rsp = rsp["output"]
        outputs = []
        for item in rsp:
            if len(item) != 5:
                continue
            s_name, s_label, predicate, o_name, o_label = item
            s_label = self.process_property_name(s_label)
            o_label = self.process_property_name(o_label)
            # force convert to OTHER_TYPE or just drop it?
            if s_label not in self.schema:
                s_label = OTHER_TYPE
            if o_label not in self.schema:
                o_label = OTHER_TYPE
            outputs.append([s_name, s_label, predicate, o_name, o_label])
        return outputs
