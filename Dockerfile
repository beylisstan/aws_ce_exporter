FROM python:3.6.5-slim
MAINTAINER Stanislav Beylis <beylis.stas@gmail.com>

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY aws_ce_exporter.py /usr/src/app/
COPY requirements.txt /usr/src/app/
RUN pip install -r requirements.txt

EXPOSE 1234

CMD [ "python3", "aws_ce_exporter.py"]

ENTRYPOINT ["python3", "aws_ce_exporter.py"]
CMD        [ "" ]

