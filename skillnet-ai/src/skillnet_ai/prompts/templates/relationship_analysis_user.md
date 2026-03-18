
Your task is to map logical relationships between the provided skills based on their names and descriptions.

You must strictly identify ONLY the following 4 types of relationships:

1. similar_to
   - A and B perform functionally equivalent tasks (e.g., "Google Search" and "Bing Search").
   - Users can replace A with B.

2. belong_to
   - A is a sub-component or specific step within B.
   - B represents a larger workflow or agent, and A is just one part of it.
   - Direction: Child -> belong_to -> Parent.

3. compose_with
   - A and B are independent but often used together in a workflow.
   - One usually produces data that the other consumes, or they are logically paired.
   - Example: "PDF Parser" compose_with "Text Summarizer".

4. depend_on
   - A CANNOT execute without B.
   - B is a hard dependency (e.g., Environment setup, API Key loader, or a core library skill).
   - Direction: Dependent -> depend_on -> Prerequisite.

Here is the list of Skills in the user's local environment. Please analyze them and generate the relationships.

Skills List:
{skills_list}

Remember:
- Be conservative. Only create a relationship if there is a logical connection based on the name and description.
- Do not hallucinate skills not in the list.

Output Format:
Return a JSON array where each element represents a relationship with the following keys:
- source: (string) The name of the source skill (the one initiating the relationship)
- target: (string) The name of the target skill (the one receiving the relationship)
- type: (string) One of the 4 relationship types: "similar_to", "belong_to", "compose_with", "depend_on"
- reason: (string) A brief explanation of why this relationship exists based on the skill descriptions.

Output Example:
[
    {{
      "source": "google_search_tool",
      "target": "bing_search_tool",
      "type": "similar_to",
      "reason": "Both provide web search capabilities and are interchangeable."
    }},
    ...
]

Keep your output in the format below:
<Skill_Relationships>
your generated JSON array here
</Skill_Relationships>
