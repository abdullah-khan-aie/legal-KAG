# Minimal data-holder stand-in for knext.reasoner.rest.models.task_stream_request.TaskStreamRequest
class TaskStreamRequest:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}
