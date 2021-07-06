#!/usr/bin/env python3
import pandas as pd
import logging
import json
import os
import argparse
import sys
from datetime import datetime
from urllib.error import HTTPError
from slack import WebClient
from slack.errors import SlackApiError
from slackeventsapi import SlackEventAdapter

pncc_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQJeJcd-fLAZbLxn0wZ9OFhUA9NTCJnNisHqBAlGnW85F4OGoNe5yYVT0RRjFA7-BIpMVOhH5DsUrWQ/pubhtml?gid=580698807&single=true&widget=false&headers=false&range=A1:W100'

def get_table(url):
    try:
        df = pd.read_html(url, header = 2)[0]
    except HTTPError:
        logging.error(f'Could not find dynamic queue sheet at {url}')
    logging.debug(df)
    return df[['ProjectID', 'Current Status', 'Technique', 'Sample Onsite?', 'Imaging Date']]

def find_current_samples(table, project):
    df = table.loc[table['ProjectID'] == project]
    logging.debug(df)

    if df.empty:
        logging.info(f'No samples found for {project}')
        return {'ready': 0, 'scheduled': []}

    samples_ready = df.loc[df['Sample Onsite?'] == 'Yes']['ProjectID'].tolist()
    samples_scheduled = df.loc[pd.notna(df['Imaging Date'])]['Imaging Date'].tolist()

    return_dict = {
        'ready': len(samples_ready),
        'scheduled': [datetime.strptime(x, '%m/%d/%Y') for x in samples_scheduled]
    }

    return_dict['scheduled'] = [x for x in return_dict['scheduled'] if x > datetime.now()]

    return return_dict

def get_old_samples(project):
    try:
        with open(f'{project}_samples.json') as infile:
            data = json.load(infile)
            logging.debug('Old JSON')
            logging.debug(data)


        data['scheduled'] = [datetime.strptime(x, '%m/%d/%Y') for x in data['scheduled']]
        data['scheduled'] = [x for x in data['scheduled'] if x > datetime.now()]
    except FileNotFoundError:
        logging.warning(f'{project}_samples.json not found. Making new empty one...')
        data = {'ready': 0, 'scheduled': []}
    
    return data

def write_samples(project, samples):
    with open(f'{project}_samples.json', 'w') as f:
        json.dump(samples, f)

def detect_changes(df, project):
    current = find_current_samples(df, project)

    old = get_old_samples(project)
    new_ready = False
    new_scheduled = False

    if current['ready'] > old['ready']:
        new_ready = current['ready'] - old['ready']
    
    if len(current['scheduled']) > len(old['scheduled']):
        new_scheduled = [x for x in current['scheduled'] if x not in old['scheduled']]

    current['scheduled'] = [x.strftime('%m/%d/%Y') for x in current['scheduled']]
    write_samples(project, current)

    logging.debug(f'Project {project}')
    logging.debug('Current:')
    logging.debug(current)
    logging.debug('Old:')
    logging.debug(old)
    logging.debug('New ready:')
    logging.debug(new_ready)
    logging.debug('New scheduled:')
    logging.debug(new_scheduled)
    return (new_ready, new_scheduled)

def make_slack_client(args):
    error_status = False

    if args.channel:
        microscopy_channel = args.channel
    else:
        try:
            microscopy_channel = os.environ['SLACK_MICROSCOPY_CHANNEL']
        except KeyError:
            logging.error('Please put your slack microscopy channel in env variable SLACK_MICROSCOPY_CHANNEL')
            error_status = True

    if args.token:
        slack_bot_token = args.token
    else:
        try:
            slack_bot_token = os.environ['SLACK_BOT_TOKEN']
        except KeyError:
            logging.error('Please put your slack bot token in env variable SLACK_BOT_TOKEN')
            error_status = True
            slack_bot_token = False

    # if the user provided a bot token we can test it even without a channel
    if error_status and not slack_bot_token:
        sys.exit(1)
    
    slack_web_client = WebClient(token=slack_bot_token)
    try:
        slack_web_client.auth_test()
    except SlackApiError:
        logging.error('Slack authentication failed. Please check your bot token.')
        error_status = True

    # we need to check this again in case setting the channel failed
    if error_status:
        sys.exit(1)
    
    return (slack_web_client, microscopy_channel)
    
def main(args):
    df = get_table(pncc_url)
    slack_web_client, microscopy_channel = make_slack_client(args)

    for project in args.project:
        
        new_ready, new_scheduled = detect_changes(df, project)
        if new_ready:
            slack_web_client.chat_postMessage(
                channel = microscopy_channel,
                text = f'You have {new_ready} new sample(s) waiting to be scheduled in project {project}'
            )

        if new_scheduled:
            formatted = [x.strftime('%m/%d/%Y') for x in new_scheduled]
            if len(formatted) == 1:
                message_text = f'A sample has been (re)scheduled for {formatted[0]} in project {project}'
            else:
                message_text = f'Samples have been (re)scheduled in project {project} for the following dates:\n{formatted}'

            slack_web_client.chat_postMessage(
                channel = microscopy_channel,
                text = message_text
            )

parser = argparse.ArgumentParser(
    description = 'Check the PNCC dynamic queue for new sample schedulings',
)
parser.add_argument(
    'project',
    nargs = '+',
    help = 'Projects to check',
    type = int
)
parser.add_argument(
    '-v', '--verbose',
    help = 'Get more informational messages',
    action = 'count',
    default = 0
)
parser.add_argument(
    '--token',
    help = 'Slack bot token. If not provided, will use SLACK_BOT_TOKEN env variable',
    type = str
)
parser.add_argument(
    '--channel',
    help = 'Slack channel ID to post to. If not provided, will use SLACK_MICROSCOPY_CHANNEL env variable',
    type = str
)

args = parser.parse_args()

levels = [logging.WARNING, logging.INFO, logging.DEBUG]
level = levels[min(len(levels) - 1, args.verbose)]
logging.basicConfig(level = level, format = '%(levelname)s: %(message)s')

if __name__ == '__main__':
    main(args)
