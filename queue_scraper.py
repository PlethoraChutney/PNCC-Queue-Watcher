import pandas as pd
import logging
import json
from datetime import datetime
from urllib.error import HTTPError

pncc_url = 'https://docs.google.com/spreadsheets/d/e/2PACX-1vQJeJcd-fLAZbLxn0wZ9OFhUA9NTCJnNisHqBAlGnW85F4OGoNe5yYVT0RRjFA7-BIpMVOhH5DsUrWQ/pubhtml?gid=580698807&amp;single=true&amp;widget=false&amp;headers=false&amp;range=A1:V100'

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
    except FileNotFoundError:
        logging.warning(f'{project}_samples.json not found. Making new empty one...')
        data = {'ready': [], 'scheduled': []}
    
    return data

def write_samples(project, samples):
    with open(f'{project}_samples.json', 'w') as f:
        json.dump(samples, f)


levels = [logging.WARNING, logging.INFO, logging.DEBUG]
# level = levels[min(len(levels) - 1, args.verbose)]
level = logging.WARNING
logging.basicConfig(level = level, format = '%(levelname)s: %(message)s')

df = get_table(pncc_url)
print(find_current_samples(df, 51815))
print(find_current_samples(df, 51325))

old = get_old_samples(51325)
print(old)
write_samples(51325, old)