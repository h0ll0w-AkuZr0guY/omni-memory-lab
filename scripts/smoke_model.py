from time import perf_counter

from omni_memory.llm.client import get_chat_model


def main() -> None:
    model = get_chat_model()
    started = perf_counter()
    response = model.invoke("请只回复：模型连接成功")
    elapsed = perf_counter() - started

    print("model_call=ok")
    print(f"elapsed_seconds={elapsed:.2f}")
    print(f"response={response.content}")


if __name__ == "__main__":
    main()
