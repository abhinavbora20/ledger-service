# Predictions for the WEB_CONCURRENCY=4 experiment

Written BEFORE running the experiment.

Hypothesis: with one worker, the single Python API process is the bottleneck.

Predictions (from the mentoring assistant):
- reads: clearly higher throughput, at least 1.3x the baseline of 610 req/s.
- transfers_spread: clearly higher throughput, at least 1.3x the baseline of 330 req/s.
- transfers_hot: little change, within about 15% of the baseline of 364 req/s, because row locks serialize those transfers whatever the number of workers.
- Falsified if: nothing improves anywhere (bottleneck is elsewhere), or transfers_hot improves as much as transfers_spread (the locking explanation is wrong).

My own predictions (write yours here before running anything):
- With 4 workers, reads and transfers_spread will be clearly faster (I guess about 2 times).
- transfers_hot may even get slightly worse, because more workers means more connections fighting over the same locks.
