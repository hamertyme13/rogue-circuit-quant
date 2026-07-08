from live.trader import AutomatedKrakenTrader


def main():
    trader = AutomatedKrakenTrader()
    trader.run_forever()


if __name__ == "__main__":
    main()
