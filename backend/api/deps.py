from fastapi import Request


def get_interview_graph(request: Request):
    return request.app.state.interview_graph


def get_tutor_graph(request: Request):
    return request.app.state.tutor_graph