# import os
# from semantic_kernel import Kernel
# from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
# from openai import AsyncOpenAI
# from dotenv import load_dotenv

# load_dotenv()


# def get_kernel() -> Kernel:
#     kernel = Kernel()
#     client = AsyncOpenAI(
#         api_key=os.getenv("OPENROUTER_API_KEY"),
#         base_url="https://openrouter.ai/api/v1",
#     )
#     kernel.add_service(
#         OpenAIChatCompletion(
#             ai_model_id=os.getenv("OPENROUTER_MODEL"),
#             async_client=client,
#         )
#     )

#     return kernel
import os
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

def get_kernel() -> Kernel:
    kernel = Kernel()

    client = AsyncOpenAI(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )

    kernel.add_service(
        OpenAIChatCompletion(
            ai_model_id=os.getenv("OPENROUTER_MODEL"),
            async_client=client,
        )
    )

    return kernel