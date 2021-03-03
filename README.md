# PNCC Dynamic Queue Watcher
## Function
A very simple script to watch the [PNCC dynamic queue](https://pncc.labworks.org/calendars/dynamic-queue).
Running this script pulls the dynamic queue spreadsheet, then checks the provided project number for samples.
It then compares the samples in the sheet to samples it found last time it ran (saved in a JSON file). If there
are new samples ready, or new samples scheduled, it informs you via slack. It then saves a new JSON file for next time.

## Installation and Use
 1. Create a virtual environment
 2. Install the necessary packages: `python -m pip install -r requirements.txt`
 3. Create a [slack app](https://api.slack.com/start)
 4. Give it permissions to send messages, and add it to your microscopy channel
 5. Create the `SLACK_BOT_TOKEN` AND `SLACK_MICROSCOPY_CHANNEL` environment variables
 6. Run the script, providing the five-digit project ID(s) you wish to monitor

Obviously, this script works best run as a cron job. The dynamic queue is updated every five minutes, so running it any more frequently than that is pointless.