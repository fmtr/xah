

from xah.settings import Settings


def main():

    Settings().run()
    from xah.harness.base import HarnessBase
    HarnessBase.launch()



if __name__ == "__main__":
    main()
