using System.Diagnostics;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using WordSearch.Api.Search;

static int EnvInt(string key, int def) =>
    int.TryParse(Environment.GetEnvironmentVariable(key), out var v) ? v : def;

int warmup = EnvInt("BENCH_WARMUP", 20);
int iters = EnvInt("BENCH_ITERS", 100);
int throughputOps = EnvInt("THROUGHPUT_OPS", 200);
string casesPath = Environment.GetEnvironmentVariable("CASES_PATH") ?? "/app/cases.json";

var dispatcher = new SearchDispatcher();
var parallel = new ParallelSearchService();
int degree = parallel.SplitDegree;

var casesJson = JsonNode.Parse(File.ReadAllText(casesPath, Encoding.UTF8))!.AsArray();

static (double medianMs, double minMs) TimeMode(Func<IReadOnlyList<string>> fn, int warmup, int iters, out int count)
{
    count = 0;
    for (int i = 0; i < warmup; i++) count = fn().Count;
    var samples = new double[iters];
    for (int i = 0; i < iters; i++)
    {
        long start = Stopwatch.GetTimestamp();
        var r = fn();
        samples[i] = Stopwatch.GetElapsedTime(start).TotalMilliseconds;
        count = r.Count;
    }
    Array.Sort(samples);
    double median = samples.Length % 2 == 0
        ? (samples[samples.Length / 2 - 1] + samples[samples.Length / 2]) / 2.0
        : samples[samples.Length / 2];
    return (median, samples[0]);
}

static IReadOnlyList<Hint> ToHints(JsonArray? arr)
{
    if (arr == null) return Array.Empty<Hint>();
    var hints = new List<Hint>();
    foreach (var h in arr)
    {
        string? letter = h?["letter"]?.GetValue<string>();
        int position = h?["position"]?.GetValue<int>() ?? 0;
        bool excluded = h?["excluded"]?.GetValue<bool>() ?? false;
        hints.Add(new Hint(position, letter, excluded));
    }
    return hints;
}

static List<string> ToLetters(JsonArray? arr)
{
    if (arr == null) return [];
    var list = new List<string>();
    foreach (var n in arr) if (n?.GetValue<string>() is string s) list.Add(s);
    return list;
}

var outCases = new List<object>();

foreach (var c in casesJson)
{
    string name = c?["name"]?.GetValue<string>() ?? "";
    string kind = c?["kind"]?.GetValue<string>() ?? "file";
    string lang = c?["lang"]?.GetValue<string>() ?? "fr";
    if (string.IsNullOrEmpty(lang)) lang = "fr";
    var hints = ToHints(c?["hints"]?.AsArray());

    var modes = new Dictionary<string, Func<IReadOnlyList<string>>>();
    if (kind == "file")
    {
        int wordLength = c?["wordLength"]?.GetValue<int>() ?? 0;
        var letters = ToLetters(c?["letters"]?.AsArray());
        bool strict = c?["strict"]?.GetValue<bool>() ?? false;
        modes["baseline"] = () => dispatcher.FileBaseline(lang, wordLength, letters, hints, strict);
        modes["indexed"] = () => dispatcher.FileDispatch(lang, wordLength, letters, hints, strict);
        modes["split"] = () => parallel.FileSplitAsync(lang, wordLength, letters, hints, strict, degree).GetAwaiter().GetResult();
    }
    else
    {
        string letters = c?["letters"]?.GetValue<string>() ?? "";
        modes["baseline"] = () => dispatcher.ManyBaseline(lang, letters, hints);
        modes["fanout"] = () => parallel.ManyFanoutAsync(lang, letters, hints).GetAwaiter().GetResult();
        modes["nested"] = () => parallel.ManyNestedAsync(lang, letters, hints, degree).GetAwaiter().GetResult();
    }

    var modeResults = new Dictionary<string, object>();
    int count = 0;
    foreach (var (mode, fn) in modes)
    {
        var (medianMs, minMs) = TimeMode(fn, warmup, iters, out count);
        modeResults[mode] = new { median_ms = medianMs, min_ms = minMs };
        Console.Error.WriteLine($"[C#] {name} / {mode}: {count} words, median {medianMs:F4} ms");
    }
    outCases.Add(new { name, kind, count, modes = modeResults });
}

// Throughput: THROUGHPUT_OPS baseline scans with CONCURRENCY threads in flight
int concurrency = EnvInt("CONCURRENCY", 16);
string tLang = "fr";
int tWordLength = 11;
var tLetters = Enumerable.Range('a', 26).Select(c => ((char)c).ToString()).ToList();
var tHints = new List<Hint> { new Hint(1, "x", false) };

// warmup
dispatcher.FileBaseline(tLang, tWordLength, tLetters, tHints, false);

var latencies = new double[throughputOps];
int tCount = 0;
var latencyLock = new object();
long tStart = Stopwatch.GetTimestamp();
var tTasks = new Task[throughputOps];
using var semaphore = new SemaphoreSlim(concurrency);
for (int i = 0; i < throughputOps; i++)
{
    int idx = i;
    await semaphore.WaitAsync();
    tTasks[idx] = Task.Run(() =>
    {
        try
        {
            long s = Stopwatch.GetTimestamp();
            var r = dispatcher.FileBaseline(tLang, tWordLength, tLetters, tHints, false);
            latencies[idx] = Stopwatch.GetElapsedTime(s).TotalMilliseconds;
            Interlocked.Exchange(ref tCount, r.Count);
        }
        finally { semaphore.Release(); }
    });
}
await Task.WhenAll(tTasks);
double tElapsed = Stopwatch.GetElapsedTime(tStart).TotalMilliseconds;
Array.Sort(latencies);
double tMedian = latencies[throughputOps / 2];
double opsPerSec = throughputOps / (tElapsed / 1000.0);
Console.Error.WriteLine($"[C#] throughput: {opsPerSec:F1} ops/s @ concurrency {concurrency}");

var report = new
{
    language = "csharp",
    label = "C#",
    meta = new { warmup, iterations = iters, split_degree = degree },
    cases = outCases,
    throughput = new
    {
        workload = "file wordLength=11 pool=26 hint=1:x (baseline scan per op)",
        concurrency,
        ops = throughputOps,
        elapsed_ms = tElapsed,
        ops_per_sec = opsPerSec,
        median_latency_ms = tMedian,
        count = tCount
    }
};

Console.WriteLine(JsonSerializer.Serialize(report));
