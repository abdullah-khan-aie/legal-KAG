# -*- coding: utf-8 -*-
# Copyright 2023 OpenSPG Authors
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except
# in compliance with the License. You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software distributed under the License
# is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.
# flake8: noqa
import json
from typing import List
from kag.interface import PromptABC


@PromptABC.register("default_query_rewrite")
class QueryRewritePrompt(PromptABC):
    template_en = {
        "instruction": """You are an expert skilled in restructuring multi-step queries. The original multi-step query has been broken down into several straightforward single-step query, each of which may explicitly (in the form of "{{i.output}}") or implicitly (such as "the person," "the city") rely on the answers to preceding queries. Please replace the references to the answers of previous queries in the provided query with the actual answers, based on the thought by the preceding queries, and rephrase the question accordingly. Refer to the example for the output format.

        
\nThe example field provides a simple example for reference. Please return only the reformulated question string IN JSON FORMAT, follow the format of  output field in the example.
        """,
        "example": {
            "input": {
                "query": "{{0.output}} has won awards, which ones have not been obtained by {{1.output}}?"
            },
            "context": {
                "0": {
                    "query": "Who played Sun Wukong in Journey to the West?",
                    "output": [
                        "Liu Xiao Ling Tong was born in 1959 and hails from Shaoxing, Zhejiang. He is a National Class-A Actor and has served as an adjunct professor at the School of Humanities, Zhejiang University. During the filming of the TV series 'Journey to the West' in 1982, he played the role of Sun Wukong throughout, winning the Best Actor Award at the 6th China Golden Eagle Awards for his performance. Answer: Liu Xiao Ling Tong"
                    ],
                },
                "1": {
                    "query": "Who sing the song 'Blue and White Porcelain'?",
                    "output": [
                        "The song 'Blue and White Porcelain' was written by Vincent Fang, composed by Jay Chou, arranged by Roger Chung, and included in Jay Chou’s eighth studio album 'I'm Busy', released on November 2, 2007. Answer: JayChou"
                    ],
                },
            },
            "output": {
                "query": "Among the awards won by Liu Xiao Ling Tong, which ones have not been won by Jay Chou?"
            },
        },
    }

    @property
    def template_variables(self) -> List[str]:
        return ["context", "query"]

    def parse_response(self, response: str, **kwargs):
        if isinstance(response, str):
            response = json.loads(response)
        if isinstance(response, list):
            response = response[0]
        if isinstance(response, dict) and "output" in response:
            response = response["output"]

        if not isinstance(response, dict):
            raise ValueError(f"response should be a dict, but got {type(response)}: {response}")
        return response
