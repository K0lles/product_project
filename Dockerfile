FROM python:3.10

WORKDIR /usr/src/app
ENV APP_DIR=/usr/src/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt update
RUN apt-get upgrade -y && apt-get -y install postgresql gcc python3-dev musl-dev
RUN pip install --no-cache-dir pipenv

COPY . $APP_DIR

RUN pipenv install
