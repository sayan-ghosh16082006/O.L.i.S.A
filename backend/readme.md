### O.L.i.S.A (Ollama Integrated Sovereign AI AGNET)

#### Folder structure
```text
project_root/
│
├── backend/
|   |── .venv/                       # virtual environment
|   |── .project_workspace/                       # the default folder where the agent will store its deliverable(cocx, ppt etc.) and other files
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # entry point (FastAPI, etc.) `STILL NOT CREATED`
│   │   ├── agent/
│   │   │   ├── __init__.py
│   │   │   ├── tools/              # the tools that the agent can use
│   │   │   │   ├── __init__.py
│   │   │   │   ├── file_handling.py
│   │   │   │   └── other_tools.py
│   │   │   ├──  planner.py              # the main agentic workflow logic
|   |   |   └── sovereignty.py           # agent logging and sovereignty logics
│   │   └── models/             
│   │   |    ├── model_manager.py          # model routing logic                     
│   │   ├── templates/   
|   |          ├── word_template.docx       # template for word document generation
│   │
│   ├── test.py
│   ├── test.ipynb   
│   │   
│   │
│   ├── requirements.txt
│   └── README.md
|   └── .gitignore
│
├── frontend/                   `STILL NOT CREATED`

```


#### NOTE :
1. Install ollama 
2. Open terminal and type to install the models
    - ollama run granite4.1:3b 
    - ollama run qwen3-vl:4b
    to exit from the chat type `/bye`
3. clone the repo
4. move into the backend folder and create a virtual environment using `python -m venv .venv`   `CREATE THE VIRTUAL ENVIRONMENT INSIDE THE BACKEND FOLDER`
5. install the dependencies using `pip install -r requirements.txt`
6. if you run the code from terminal make sure to activate the virtual environment using `.venv/Scripts/activate` (for windows) and run the code within the backend folder only or use code runner's **run file in deditated terminal** option.
7. Beore merging and commititng make sure to test yur code and then only commit the changes to the repo.
8. while commiting after the commit message add your title for reference.
9. first time while running the a dynamic model selection section will appear, fill it and it will create a model_config.json file in the backend folder. After that it will not appear again unless you delete the model_config.json file.
10. I have pushed the code in `master branch` so follow and always push from the root folder not from backend or frontend the steps
    - `git clone <repo_url>` and check if the branch name is `master` , if not then change it to master using `git checkout master`
    - `git add .`
    - `git commit -m "your commit message(title)"`
    - `git push origin master`
    - from the next time onwards you can directly pull the changes using `git pull origin master` and then push your changes.
