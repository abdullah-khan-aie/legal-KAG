import json

from kag.interface import PromptABC


@PromptABC.register("semantic_seg")
class SemanticSegPrompt(PromptABC):
    template_en = """
{
    "instruction": "\nPlease understand the content of the text in the input field, recognize the structure and components of the text, and determine the segmentation points according to the semantic theme, dividing it into several non-overlapping sections. If the article has recognizable structural information such as chapters, please divide it according to the top-level structure.\nPlease return the results according to the schema definition, including summaries and starting points of the sections. The format must be a JSON string. Please follow the examples given in the example field.",
    "schema": {
        "Section Summary": "A brief summary of the section text",
        "Section Starting Point": "The starting point of the section in the original text, limited to about 20 characters. This segmentation point will be used to split the original text, so it must be found in the original text!"
    },
    "input": "$input",
    "example": [
        {
            "input": "Jay Chou (Jay Chou), born on January 18, 1979, in Xinbei City, Taiwan Province, originally from Yongchun County, Fujian Province, is a Mandopop male singer, musician, actor, director, screenwriter, and a graduate of Tamkang Senior High School.\nIn 2000, recommended by Yang Junrong, Jay Chou started singing his own compositions.",
            "output": [
                {
                    "Section Summary": "Personal Introduction",
                    "Section Starting Point": "Jay Chou (Jay Chou), born on January 18"
                },
                {
                    "Section Summary": "Career Start",
                    "Section Starting Point": "\nIn 2000, recommended by Yang Junrong"
                }
            ]
        },
        {
            "input": "Hangzhou Flexible Employment Personnel Housing Provident Fund Management Measures (Trial)\nTo expand the benefits of the housing provident fund system and support flexible employment personnel to solve housing problems, according to the State Council's 'Housing Provident Fund Management Regulations', 'Zhejiang Province Housing Provident Fund Regulations' and the relevant provisions and requirements of the Ministry of Housing and Urban-Rural Development and the Zhejiang Provincial Department of Housing and Urban-Rural Development on flexible employment personnel participating in the housing provident fund system, combined with the actual situation in Hangzhou, this method is formulated.\n1. This method applies to the voluntary deposit, use, and management of the housing provident fund for flexible employment personnel within the administrative region of this city.\n2. The flexible employment personnel referred to in this method are those who are within the administrative region of this city, aged 16 and above, and males under 60 and females under 55, with full civil capacity, and employed in a flexible manner such as part-time, self-employed, or in new forms of employment.\n3. Flexible employment personnel applying to deposit the housing provident fund should apply to the Hangzhou Housing Provident Fund Management Center (hereinafter referred to as the Provident Fund Center) for deposit registration procedures and set up personal accounts.",
            "output": [
                {
                    "Section Summary": "Background and Basis for Formulating the Management Measures",
                    "Section Starting Point": "To expand the benefits of the housing provident fund system"
                },
                {
                    "Section Summary": "Scope of Application of the Management Measures",
                    "Section Starting Point": "1. This method applies to the voluntary deposit"
                },
                {
                    "Section Summary": "Definition of Flexible Employment Personnel",
                    "Section Starting Point": "2. The flexible employment personnel referred to in this method"
                },
                {
                    "Section Summary": "Procedures for Flexible Employment Personnel to Register for Deposit",
                    "Section Starting Point": "3. Flexible employment personnel applying to deposit the housing provident fund"
                }
            ]
        }
    ]
}
    """

    @property
    def template_variables(self) -> list[str]:
        return ["input"]

    def parse_response(self, response: str, **kwargs):
        if isinstance(response, str):
            response = json.loads(response)
        if isinstance(response, dict) and "output" in response:
            response = response["output"]

        content = kwargs.get("input", "")

        seg_info = []
        for seg_point in response:
            if not isinstance(seg_point, dict):
                continue
            start = seg_point.get(
                "Section Starting Point",
            )
            if not isinstance(start, str):
                continue
            start = start.strip()
            loc = content.find(start)
            if loc == -1:
                print(f"incorrect seg: {seg_point}")
                continue

            abstract = seg_point.get("Section Summary", None)
            seg_info.append((loc, abstract))
        return seg_info
