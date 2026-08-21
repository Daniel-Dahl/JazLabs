from JazLabs.hardware.TimeTagger.TimeTagger_Client import TimeTaggerClient


time_tagger_client = None

try:
    time_tagger_client = TimeTaggerClient(
        host="127.0.0.1",
        command_port=50931,
        timeout_ms=120_000,
        client_id="time_tagger_example",
    )

    time_tagger_client.SetTriggerLevel(channel=1, voltage=0.5)
    time_tagger_client.SetTriggerLevel(channel=2, voltage=0.5)

    coincidence_result = time_tagger_client.MeasureCoincidences(
        channels=[1, 2],
        coincidence_window=100,
        counting_time=1.0,
    )
    print(coincidence_result)
finally:
    if time_tagger_client is not None:
        time_tagger_client.close()
