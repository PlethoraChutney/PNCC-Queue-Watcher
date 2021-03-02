import pandas as pd
import logging
import json
import os
from datetime import datetime
from urllib.error import HTTPError
from slack import WebClient
from slack.errors import SlackApiError
from slackeventsapi import SlackEventAdapter

pncc_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQJeJcd-fLAZbLxn0wZ9OFhUA9NTCJnNisHqBAlGnW85F4OGoNe5yYVT0RRjFA7-BIpMVOhH5DsUrWQ/pubhtml?gid=580698807&amp;single=true&amp;widget=false&amp;headers=false&amp;range=A1:V100'
microscopy_channel = 'CAR3BED5L'

def get_table(url):
    try:
        df = pd.read_html(url, header = 2)[1]
    except HTTPError:
        logging.error(f'Could not find dynamic queue sheet at {url}')
    return df[['ProjectID', 'Current Status', 'Technique', 'Sample Onsite?', 'Imaging Date']]

def find_current_samples(table, project):
    df = table.loc[table['ProjectID'] == project]
    logging.debug(df)

    if df.empty:
        logging.info(f'No samples found for {project}')
        return None

    samples_ready = df.loc[df['Sample Onsite?'] == 'Yes']['ProjectID'].tolist()
    samples_scheduled = df.loc[pd.notna(df['Imaging Date'])]['Imaging Date'].tolist()

    return {
        'ready': len(samples_ready),
        'scheduled': [datetime.strptime(x, '%m/%d/%Y') for x in samples_scheduled]
    }

def get_old_samples(project):
    try:
        with open(f'{project}_samples.json') as infile:
            data = json.load(infile)

        data['scheduled'] = [datetime.strptime(x, '%m/%d/%Y') for x in data['scheduled']]
        data['scheduled'] = [x for x in data['scheduled'] if x < datetime.now()]
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

    return (new_ready, new_scheduled)

def main(project):
    df = get_table(pncc_url)

    new_ready, new_scheduled = detect_changes(df, project)

    slack_web_client = WebClient(token=os.environ['SLACK_BOT_TOKEN'])


    if new_ready:
        slack_web_client.chat_postMessage(
            channel = microscopy_channel,
            text = f'You have {new_ready} sample(s) waiting to be scheduled in project {project}'
        )

    if new_scheduled:
        formatted = [x.strftime('%m/%d/%Y') for x in new_scheduled]
        if len(formatted) == 1:
            slack_web_client.chat_postMessage(
                channel = microscopy_channel,
                text = f'A sample has been (re)scheduled for {formatted[0]}'
            )
        else:
            slack_web_client.chat_postMessage(
                channel = microscopy_channel,
                text = f'Samples have been (re)scheduled: {formatted}'
            )
        


levels = [logging.WARNING, logging.INFO, logging.DEBUG]
# level = levels[min(len(levels) - 1, args.verbose)]
level = logging.WARNING
logging.basicConfig(level = level, format = '%(levelname)s: %(message)s')

if __name__ == '__main__':
    main(51709)