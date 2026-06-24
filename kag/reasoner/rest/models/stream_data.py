# Minimal data-holder stand-in for knext.reasoner.rest.models.stream_data.StreamData
class StreamData:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}
