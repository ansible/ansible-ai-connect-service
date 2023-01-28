from typing import Any, Dict

def camel_to_snake(name: str) -> str:
    snake_case = ""
    for item in range(len(name)):
        if name[item].isupper() and item > 0:
            if name[item-1].islower():
                snake_case += "_"
        snake_case += name[item].lower()
    return snake_case

def convert_keys(original_dict: Dict[str, Any]) -> Dict[str, Any]:
    converted_dict = {}
    for key in original_dict.keys():
        snake_key = camel_to_snake(key)
        converted_dict[snake_key] = original_dict[key]
    return converted_dict
