import os
import subprocess
from pathlib import Path
import json
from langchain_ollama import ChatOllama
from langchain_huggingface import HuggingFaceEndpoint


class ModelManager:

    def __init__(self, provider : str, mapping_file : str = "model_config.json"):
        self.provider = provider
        self.models = self.discover_model(provider)
        self.mapping_file = Path(mapping_file)
        self.model_capability_mapping = self.load_or_create_mapping()




    def discover_model(self ,provider : str):
        if provider == "ollama":
            result = subprocess.run(["ollama", "list"], capture_output=True, text = True)
            return ([line.split()[0] for line in result.stdout.splitlines()[1:]])

        elif provider == "huggingface":
            cache_dir = os.path.expanduser("~/.cache/huggingface/transformers")
            return os.listdir(cache_dir)
        elif provider == "lmstudio":
            return os.listdir("path/to/lmstudio/models")
        else:
            return []




    def load_or_create_mapping(self):

        if (self.mapping_file.exists()):
            with open(self.mapping_file, "r") as f:
                model_mapping = json.load(f)
            for task, model in model_mapping.items():
                if model not in self.models:
                    raise ValueError(f"The provider {self.provider} has no model named {model}")

            return model_mapping
        else:
            print("Provider name : ", self.provider)
            print("Discovered models:")
            for idx, model in enumerate(self.models):
                print(f"{idx}. {model}")

            cwd = Path.cwd()

            template = {
                            "coding": "",
                            "summarization": "",
                            "vision": "",
                            "embedding" : "",
                            "multimodal" : ""
                        }
            for i in template.keys():
                print(i + " : ", end = "")
                template[i] = input()

            file_path = cwd / "model_config.json"

            with open(file_path, "w") as f:
                json.dump(template, f, indent = 4)

            print(f"Model configuration successfull: {self.mapping_file}")
            return template




    def get_model(self, task_type):
        model_name = self.model_capability_mapping.get(task_type)
        if not model_name:
            raise ValueError(f"No model found for task type: {task_type}")

        elif self.provider == "ollama":
            return ChatOllama(model = model_name)

        elif self.provider == "huggingface":
            
            return HuggingFaceEndpoint(model=model_name)