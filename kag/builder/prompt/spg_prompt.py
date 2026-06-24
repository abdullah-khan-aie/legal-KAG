#
import copy
import json
import logging

from kag_extracted.interface import PromptABC
from kag_extracted.schema.client import (
    OTHER_TYPE,
    ConstraintTypeEnum,
    SchemaClient,
    SpgTypeEnum,
    SPGTypeName,
)

# original: from kag.builder.model.spg_record import SPGRecord (server record).
# Used only in return-type hints below; aliased to dict to drop the server dep.
SPGRecord = dict

logger = logging.getLogger(__name__)


class SPGPrompt(PromptABC):
    """
    Base class for generating SPG schema-based entity/event extraction prompts.

    Attributes:
        ignored_types (List[str]): List of SPG types to be ignored.
        ignored_properties (List[str]): List of properties to be ignored.
        default_properties (Dict[str, str]): Default properties for SPG types.
        ignored_relations (List[str]): List of relations to be ignored.
    """

    ignored_types: list[str] = ["Chunk"]
    ignored_properties: list[str] = [
        "id",
        "stdId",
        "desc",
        "description",
        "eventTime",
    ]
    default_properties: dict[str, str] = {
        "name": "Text",
    }

    ignored_relations: list[str] = ["isA"]

    def __init__(
        self,
        spg_type_names: list[SPGTypeName] = [],
        language: str = "",
        **kwargs,
    ):
        """
        Initializes the SPGPrompt instance.

        Args:
            spg_type_names (List[SPGTypeName], optional): List of SPG type names. Defaults to [].
            language (str, optional): Language for the prompt. Defaults to "".
            **kwargs: Additional keyword arguments.
        """
        super().__init__(language=language, **kwargs)
        self.schema = SchemaClient(schema_path=kwargs.get("schema_path")).load()
        self.spg_type_names = spg_type_names
        if not spg_type_names:
            self.spg_types = self.schema
        else:
            self.spg_types = {k: v for k, v in self.schema.items() if k in spg_type_names}
        self.create_prompt_schema()
        # self._init_render_variables()

    @property
    def template_variables(self) -> list[str]:
        """
        Returns the list of template variables used in the prompt.

        Returns:
            List[str]: List of template variables.
        """
        return ["schema", "input"]

    def get_accept_types(self):
        """
        Returns the list of accepted SPG types.

        Returns:
            List[SpgTypeEnum]: List of accepted SPG types.
        """
        return [
            SpgTypeEnum.Entity,
            SpgTypeEnum.Concept,
            SpgTypeEnum.Event,
        ]

    def build_prompt(self, variables: dict[str, str]) -> str:
        """
        Builds the prompt using the provided variables.

        Args:
            variables (Dict[str, str]): Dictionary of variables to be used in the prompt.

        Returns:
            str: The built prompt.
        """
        return super().build_prompt(
            {
                "schema": copy.deepcopy(self.prompt_schema),
                "input": variables.get("input"),
            }
        )

    def process_property_name(self, name: str):
        """
        Process property name by removing descriptions enclosed in parentheses.
        Args:
            name (dict):  property names (possibly containing descriptions in parentheses)

        Returns:
            str: A new string having the descriptions in parentheses removed.

        Example:
            >>> name = 'authors(authors of work, such as director, actor, lyricist, composer and singer)'
            >>> process_property_name(input_properties)
            'authors'
        """

        return name.split("(")[0]

    def process_property_names(self, properties: dict):
        """
        Process property names by removing descriptions enclosed in parentheses.

        This method iterates through the given dictionary of properties, removes any
        descriptions enclosed in parentheses from the property names, and returns a new
        dictionary with the processed names. If a property value is itself a dictionary,
        this method will recursively process it.

        Args:
            properties (dict): A dictionary where keys are property names (possibly containing
                               descriptions in parentheses) and values are either property values
                               or nested dictionaries.

        Returns:
            dict: A new dictionary with the same structure as the input, but with all property
                  names having their descriptions in parentheses removed.
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
        """
        Parses the response string into a list of SPG records.

        Args:
            response (str): The response string to be parsed.
            **kwargs: Additional keyword arguments.

        Returns:
            List[SPGRecord]: List of parsed SPG records.
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
        """
        Creates the schema for extraction prompt based on the project schema.
        """
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
    template_zh: dict = {
        "instruction": "As an expert in graph knowledge extraction, you need to extract all entities and their properties from the text in the input field based on a schema that defines entity types and their corresponding attributes. Attributes marked as List in the schema should return a list, and attributes not extracted should return null. Output the results in a standard JSON list format, where each element in the list is in the form of {category: properties}. You can refer to the example format provided in the example field. Note that the SemanticType of an entity attribute refers to a more specific and clearly defined type compared to the entity type itself, such as Professor or Actor for the Person type.",
        "example": [
            {
                "input": "Jay Chou, born on January 18, 1979, in New Taipei City, Taiwan Province, with ancestral roots in Yongchun County, Fujian Province, is a renowned male singer, musician, actor, director, and screenwriter in the realm of Chinese pop music. He graduated from Tamkang High School. In 2000, he released his debut solo album, <Jay> [26]. In 2023, he won three major awards at the inaugural Wave Music Awards for Best Production, Best Composition, and Best Music Video for The Greatest Work.",
                "output": [
                    {
                        "category": "Person",
                        "properties": {
                            "name": "Jay Chou",
                            "semanticType": "Musician",
                            "description": "a renowned male singer, musician, actor, director, and screenwriter in Chinese pop music",
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
                            "description": "Jay Chou's ancestral home",
                        },
                    },
                    {
                        "category": "Organization",
                        "properties": {
                            "name": "Tamkang High School",
                            "semanticType": "School",
                            "description": "the school Jay Chou graduated from",
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
                            "semanticType": "MusicVideo",
                            "description": "the work for which Jay Chou won multiple music awards",
                        },
                    },
                ],
            }
        ],
    }

    template_en: dict = {
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

    def get_accept_types(self):
        return [
            SpgTypeEnum.Entity,
            SpgTypeEnum.Concept,
        ]


@PromptABC.register("spg_event")
class SPGEventPrompt(SPGPrompt):
    template_zh: dict = {
        "instruction": "As an expert in knowledge graph event extraction, you need to extract all events and their attributes from the text in the input field based on the defined event types and corresponding attribute schema. For attributes marked as List in the schema, return them as a list, and for attributes that cannot be extracted, return null. Output in the standard JSON list format, with each element in the list having the form {category: properties}. You can refer to the example format provided in the example field.",
        "example": {
            "input": "In 1986, Stephen Chow was transferred to the drama department of TVB. In the same year, he played the role of Pan Jiawei, a lovable, lively, and slightly shy character, in the episodic situational comedy <My Brother's Girlfriend>; this was his first time taking on a lead role in a sitcom. Later, he also had minor roles in TV series starring actors such as Anthony Wong and Aaron Kwok.",
            "output": [
                {
                    "category": "Event",
                    "properties": {
                        "name": "Stephen Chow was transferred to the drama department of TVB",
                        "abstract": "In 1986, Stephen Chow was transferred to the drama department of TVB.",
                        "subject": "Stephen Chow",
                        "time": "1986",
                        "location": "TVB",
                        "participants": [],
                        "semanticType": "Transfer",
                    },
                },
                {
                    "category": "Event",
                    "properties": {
                        "name": "Stephen Chow played Pan Jiawei in My Brother's Girlfriend",
                        "abstract": "In 1986, Stephen Chow played the role of Pan Jiawei, a lovable, lively, and slightly shy character, in the episodic situational comedy <My Brother's Girlfriend>; this was his first time taking on a lead role in a sitcom.",
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
                        "abstract": "In 1986, Stephen Chow had minor roles in TV series starring actors such as Anthony Wong and Aaron Kwok.",
                        "subject": "Stephen Chow",
                        "time": "1986",
                        "location": None,
                        "participants": ["Anthony Wong", "Aaron Kwok"],
                        "semanticType": "Performance",
                    },
                },
            ],
        },
    }

    template_en: dict = {
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

    def get_accept_types(self):
        return [
            SpgTypeEnum.Event,
        ]


@PromptABC.register("spg_relation")
class SPGRelationPrompt(SPGPrompt):
    template_zh: dict = {
        "instruction": "You are an expert in Open Information Extraction (OpenIE). The schema defines the entity types you need to focus on, along with optional type explanations enclosed in parentheses. entity_list is a set of entities. Please extract any possible [subject entity, subject entity type, predicate, object entity, object entity type] quintuples from the text in the input field and list them in JSON list format. Please strictly follow these requirements:\n1. At least one of the subject entity and the object entity should be included in entity_list, but it is not required that both are.\n2. The subject and object entity types must be types defined in the schema; otherwise they are invalid.\n3. Resolve pronouns to their corresponding names explicitly to maintain clarity.",
        "example": {
            "input": "In 1986, Stephen Chow was transferred to the drama department of TVB. In the same year, he played the lovable, lively, and slightly shy Pan Jiawei in the situational comedy <My Brother's Girlfriend>, which was also his first time as the male lead in a sitcom. Later, he also appeared as an extra in TV series starring Anthony Wong, Aaron Kwok, and others.",
            "entity_list": [
                {"name": "Stephen Chow", "category": "Person"},
                {"name": "TVB", "category": "Organization"},
                {"name": "My Brother's Girlfriend", "category": "Works"},
                {"name": "Pan Jiawei", "category": "Person"},
                {"name": "Anthony Wong", "category": "Person"},
                {"name": "Aaron Kwok", "category": "Person"},
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
                ["Stephen Chow", "Person", "co-starred with", "Anthony Wong", "Person"],
                ["Stephen Chow", "Person", "co-starred with", "Aaron Kwok", "Person"],
                [
                    "Stephen Chow",
                    "Person",
                    "appeared as an extra in",
                    "TV series starring Anthony Wong, Aaron Kwok, and others",
                    "Works",
                ],
            ],
        },
    }

    template_en: dict = {
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

    def get_accept_types(self):
        """
        Returns the list of accepted SPG types.

        Returns:
            List[SpgTypeEnum]: List of accepted SPG types.
        """
        return [
            SpgTypeEnum.Entity,
            SpgTypeEnum.Concept,
        ]

    def build_prompt(self, variables: dict[str, str]) -> str:
        """
        Builds the prompt using the provided variables.

        Args:
            variables (Dict[str, str]): Dictionary of variables to be used in the prompt.

        Returns:
            str: The built prompt.
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
        """
        Parses the response string into a list of SPG records.

        Args:
            response (str): The response string to be parsed.
            **kwargs: Additional keyword arguments.

        Returns:
            List[SPGRecord]: List of parsed SPG records.
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
