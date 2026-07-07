import pandas as pd


class DataSplitter:

    def __init__(self, train_ratio=0.70):
        self.train_ratio = train_ratio

    def split(self, df: pd.DataFrame):

        split = int(len(df) * self.train_ratio)

        train = df.iloc[:split].copy()

        test = df.iloc[split:].copy()

        return train, test