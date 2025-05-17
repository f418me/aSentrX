from truthbrush import Api

api = Api()

statuses = api.pull_statuses(
    username="realDonaldTrump",
    replies=False,
    verbose=True,
    since_id='114499337476531986'
)

for status in statuses:
    print(status)
    print(status["content"])