Q1: TOKEN LIMIT EXCEEDED
S: text-davinci-002 和 text-davinci-003 模型已经不支持了, 可用模型见[https://platform.openai.com/docs/deprecations], 暂时替换为 davinci-002(建议换babbage-002, davinci-002太贵了, 用完才看到),换模型应该会遇到Q2

Q2: IndexError: list index out of range
S: 模型响应内容有关, 在文件`reverie/backend_server/persona/prompt_template/run_gpt_prompt.py --> __func_clean_up`, 建议报错时在函数中加入以下代码, 保存有问题数据方便调试(省钱)

    ```python
    with open(save_path, 'w') as f:
        fp.write(gpt_response)
    ```

`utils.py` 文件需要改动为
```python
import os
DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = DIR.split('/reverie/')[0]

# Copy and paste your OpenAI API Key
openai_api_key = "key"
# Put your name
key_owner = "<Name>"

maze_assets_loc = f"{ROOT}/environment/frontend_server/static_dirs/assets"
env_matrix = f"{maze_assets_loc}/the_ville/matrix"
env_visuals = f"{maze_assets_loc}/the_ville/visuals"

fs_storage = f"{ROOT}/environment/frontend_server/storage"
fs_temp_storage = f"{ROOT}/environment/frontend_server/temp_storage"

collision_block_id = "32125"

# Verbose 
debug = True
```

