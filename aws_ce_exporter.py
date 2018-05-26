from os import getenv
from datetime import datetime, timedelta
import boto3
from prometheus_client import start_http_server, Gauge
import schedule
import argparse
import time
import logging
import sys

# Add logic for granularity
parser = argparse.ArgumentParser(description='aws_ce_exporter scrapes metrics from AWS COST EXPLORER on daily bases')
parser.add_argument('-g', '--granularity', help='granularity', default='DAILY')
parser.add_argument('-t', '--time', help='time when exporter scrapes metrics format: "[0-24]:[0-59]"', default="11:21")
parser.add_argument('-m', '--metrics', help='metrics', default=[
                                                                  'BlendedCost',
                                                                  'UnblendedCost',
                                                                  'UsageQuantity',
                                                              ])
parser.add_argument('-dl', '--dimensions_list', help='dimensions_list', default=['LINKED_ACCOUNT', 'REGION'])
parser.add_argument('-gb', '--group_by', help='group_by', default=[
                                                                        {
                                                                            'Type': 'TAG',
                                                                            'Key': 'Name'
                                                                        },
                                                                        {
                                                                            'Type': 'DIMENSION',
                                                                            'Key': 'SERVICE'
                                                                        },
                                                                    ])
args = vars(parser.parse_args())
granularity = args["granularity"]
attimne = args["time"]
metrics = args["metrics"]
dimensions_list = args["dimensions_list"]
group_by = args["group_by"]


def setup_custom_logger(name):
    formatter = logging.Formatter(fmt='%(asctime)s %(levelname)-8s %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler = logging.FileHandler('aws_ce_exporter.log', mode='w')
    handler.setFormatter(formatter)
    screen_handler = logging.StreamHandler(stream=sys.stdout)
    screen_handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.addHandler(screen_handler)
    return logger


def get_dimensions(dimensions_list, timeperiod):
    dimensions_dict = {}
    for dimension in dimensions_list:
        response = client.get_dimension_values(
            TimePeriod=timeperiod,
            Dimension=dimension,
            Context='COST_AND_USAGE'
        )
        dimensions_dict[dimension] = response['DimensionValues']
    return dimensions_dict


def get_labels_names(filter, groupby):
    labels_names = []
    for k in filter.keys():
        for l in filter[k]:
            labels_names.append(l["Dimensions"]["Key"])
    for d in groupby:
        label_name = ''
        for k in d.keys():
            if label_name is '':
                label_name = d[k]
            else:
                label_name = label_name + '_' + d[k]
        labels_names.append(label_name)

    labels_names = [x.lower() for x in labels_names]
    return labels_names


def create_gauges(metrics_names, labels_names):
    for metric_name in metrics_names:
        gauges[metric_name] = Gauge(metric_name, metric_name, list(labels_names))
    return gauges


def update_gauges(filter, response):
    for group in response['ResultsByTime'][0]['Groups']:
        labels_values = []
        for k in filter.keys():
            for l in filter[k]:
                labels_values.append(l["Dimensions"]["Values"][0])
        for key in group['Keys']:
            key = key.replace('Name$', '')
            labels_values.append(key)
        for metric_name, amount_unit in group['Metrics'].items():
            gauges[metric_name].labels(*labels_values).set(amount_unit['Amount'])


def job(metrics, granularity, dimensions_list, groupby):
    logger.info('Job started')

    timeperiod = {
                     'Start': datetime.strftime(datetime.now() - timedelta(1), '%Y-%m-%d'),
                     'End': datetime.strftime(datetime.now(), '%Y-%m-%d')
                 }
    dimensions_dict = get_dimensions(dimensions_list, timeperiod)
    keyList = sorted(dimensions_dict.keys())
    for i, k in enumerate(keyList):
        if len(keyList) > i+1:
            for v1 in dimensions_dict[keyList[i]]:
                for v2 in dimensions_dict[keyList[i+1]]:
                    key1 = keyList[i]
                    value1 = v1['Value']
                    key2 = keyList[i+1]
                    value2 = v2['Value']
                    filter = {
                                 "And": [
                                     {
                                         "Dimensions": {
                                             "Key": key1,
                                             "Values": [
                                                 value1
                                             ]
                                         }
                                     },
                                     {
                                         "Dimensions": {
                                             "Key": key2,
                                             "Values": [
                                                 value2
                                             ]
                                         }
                                     }
                                 ]
                             }

                    response = client.get_cost_and_usage(
                        TimePeriod=timeperiod,
                        Granularity=granularity,
                        Filter=filter,
                        Metrics=metrics,
                        GroupBy=groupby
                    )

                    labels_names = get_labels_names(filter, groupby)
                    if len(gauges) is 0:
                        create_gauges(metrics, labels_names)
                    update_gauges(filter, response)

    logger.info('Job finished')


def main():
    global logger
    logger = setup_custom_logger('aws_ce')
    global client
    client = boto3.client('ce')
    global gauges
    gauges = {}

    start_http_server(1234)

    schedule.every().day.at(attimne).do(job, metrics, granularity, dimensions_list, group_by)

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    main()