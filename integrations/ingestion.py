from typing import List

import httpx

from utils.exceptions import SemanticSearchAPIException


class SemanticSearch:
    """Class to handle semantic search API calls."""

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def call_knowledge_base_search(self, query: str, knowledge_base_id: List[int], team_id: str, user_id: str,
                                         org_id: str):
        """Call the updated semantic search API asynchronously."""
        try:
            payload = {
                "query": query,
                "knowledge_base_id": knowledge_base_id,
                "top_answer_count": 8,
                "matching_percentage": 70.0,
                "team_id": str(team_id or ''),
                "user_id": str(user_id or ''),
                "org_id": str(org_id or '')
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'{self.base_url}/v1.0/kb/vector-search',
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                )

                if response.status_code != 200:
                    return "Data not found!"

                return response.json()["data"]
        except Exception as e:
            raise SemanticSearchAPIException(str(e))

    async def call_folder_structure(self, graph_id: str):
        """Call the updated semantic search API asynchronously."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f'{self.base_url}/v1.0/get-folder-structure/{graph_id}',
                    headers={'Content-Type': 'application/json'}
                )

                if response.status_code != 200:
                    return "Data not found!"

                return response.json()["data"]
        except Exception as e:
            raise SemanticSearchAPIException(str(e))

    async def call_keyword_search(self, keywords: List[str], graph_id: str, files: list = None, folders: list = None):
        """Call the updated semantic search API asynchronously."""
        try:
            payload = {
                "graph_id": graph_id,
                "keywords": keywords,
                "max_results": 10,
                "file_paths": files if files else [],
                "folder_paths": folders if folders else [],
                "entire_workspace": not (files or folders)
            }
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'{self.base_url}/v1.0/get-keyword-search',
                    json=payload,
                    headers={'Content-Type': 'application/json'}
                )

                if response.status_code != 200:
                    return "Data not found!"

                return response.json()["data"]
        except Exception as e:
            raise SemanticSearchAPIException(str(e))
