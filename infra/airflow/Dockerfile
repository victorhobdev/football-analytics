FROM apache/airflow:2.9.3

USER airflow

COPY infra/airflow/requirements.txt /tmp/airflow-requirements.txt

RUN pip install --no-cache-dir -r /tmp/airflow-requirements.txt
