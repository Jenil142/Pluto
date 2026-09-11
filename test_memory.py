import asyncio
import cognee


async def main():
    print("Saving memory...")

    await cognee.remember(
        "Jenil is building a personal AI assistant called Pluto."
    )

    print("Memory saved.")

    print("Recalling memory...")

    result = await cognee.recall(
        "What personal AI assistant is Jenil building?"
    )

    print("\nRecall result:")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
