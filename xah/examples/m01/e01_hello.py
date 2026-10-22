from xah import Harness


class HelloWorld(Harness):
    # (1)!
    instructions = 'You are an agent who only says "Hello World"!'


if __name__ == "__main__":
    HelloWorld.launch()
