package com.lab.search;

import com.lab.search.model.Hint;
import com.lab.search.service.WordSearchService;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

/// In-process benchmark for the Java implementation. Runs the algorithm directly
/// (no HTTP), timing each canonical case per concurrency mode with warmup +
/// median-of-N, and prints a single JSON report to stdout (logs go to stderr).
///
/// Launched as a plain main (no Spring context) via the Boot jar's
/// PropertiesLauncher, so stdout carries only the JSON report:
/// ```
/// java -Dloader.main=com.lab.search.BenchmarkRunner -cp app.jar \
///      org.springframework.boot.loader.launch.PropertiesLauncher
/// ```
public final class BenchmarkRunner {

    private static final JsonMapper MAPPER = JsonMapper.builder().build();

    private static int envInt(String key, int def) {
        String v = System.getenv(key);
        try {
            return v != null && !v.isEmpty() ? Integer.parseInt(v) : def;
        } catch (NumberFormatException e) {
            return def;
        }
    }

    private static List<Hint> toHints(JsonNode arr) {
        List<Hint> hints = new ArrayList<>();
        if (arr != null) {
            for (JsonNode h : arr) {
                String car = h.hasNonNull("car") ? h.get("car").asText() : null;
                hints.add(new Hint(h.path("pos").asInt(), car, h.path("inverted").asBoolean(false)));
            }
        }
        return hints;
    }

    private record Timing(double medianMs, double minMs) {}

    private static Timing timeMode(Supplier<List<String>> fn, int warmup, int iters, int[] outCount) {
        for (int i = 0; i < warmup; i++) outCount[0] = fn.get().size();
        double[] samples = new double[iters];
        for (int i = 0; i < iters; i++) {
            long start = System.nanoTime();
            List<String> r = fn.get();
            samples[i] = (System.nanoTime() - start) / 1_000_000.0;
            outCount[0] = r.size();
        }
        Arrays.sort(samples);
        double median = samples[samples.length / 2];
        if (samples.length % 2 == 0) {
            median = (samples[samples.length / 2 - 1] + samples[samples.length / 2]) / 2.0;
        }
        return new Timing(median, samples[0]);
    }

    // runThroughput runs THROUGHPUT_OPS baseline scans with CONCURRENCY threads
    // in flight, reporting aggregate ops/sec and median per-op latency.
    private static Map<String, Object> runThroughput(WordSearchService service) throws Exception {
        int concurrency = envInt("CONCURRENCY", 16);
        int ops = envInt("THROUGHPUT_OPS", 200);
        String lang = "fr";
        int nbCar = 11;
        List<String> letters = new ArrayList<>();
        for (char c = 'a'; c <= 'z'; c++) letters.add(String.valueOf(c));
        List<Hint> hints = List.of(new Hint(1, "x", false));

        service.fileBaseline(lang, nbCar, letters, hints, false); // warmup

        double[] latencies = new double[ops];
        AtomicInteger count = new AtomicInteger();
        ExecutorService ex = Executors.newFixedThreadPool(concurrency);
        long start = System.nanoTime();
        List<Future<?>> futures = new ArrayList<>();
        for (int i = 0; i < ops; i++) {
            final int idx = i;
            futures.add(ex.submit(() -> {
                long t = System.nanoTime();
                List<String> r = service.fileBaseline(lang, nbCar, letters, hints, false);
                latencies[idx] = (System.nanoTime() - t) / 1_000_000.0;
                count.set(r.size());
            }));
        }
        for (Future<?> f : futures) f.get();
        ex.shutdown();
        double elapsed = (System.nanoTime() - start) / 1_000_000.0;
        Arrays.sort(latencies);

        Map<String, Object> m = new LinkedHashMap<>();
        m.put("workload", "file nb_car=11 pool=26 hint=1:x (baseline scan per op)");
        m.put("concurrency", concurrency);
        m.put("ops", ops);
        m.put("elapsed_ms", elapsed);
        m.put("ops_per_sec", ops / (elapsed / 1000.0));
        m.put("median_latency_ms", latencies[ops / 2]);
        m.put("count", count.get());
        return m;
    }

    public static void main(String[] args) throws Exception {
        int warmup = envInt("BENCH_WARMUP", 20);
        int iters = envInt("BENCH_ITERS", 100);
        String casesPath = System.getenv().getOrDefault("CASES_PATH", "/app/cases.json");

        WordSearchService service = new WordSearchService();
        int degree = service.splitDegree();
        JsonNode cases = MAPPER.readTree(Files.readString(Path.of(casesPath)));

        List<Map<String, Object>> outCases = new ArrayList<>();
        for (JsonNode c : cases) {
            String name = c.path("name").asText();
            String kind = c.path("kind").asText("file");
            String lang = c.path("lang").asText("fr");
            if (lang.isEmpty()) lang = "fr";
            List<Hint> hints = toHints(c.get("lst_hint"));

            Map<String, Supplier<List<String>>> modes = new LinkedHashMap<>();
            if (kind.equals("file")) {
                int nbCar = c.path("nb_car").asInt();
                List<String> lstCar = new ArrayList<>();
                if (c.has("lst_car")) c.get("lst_car").forEach(n -> lstCar.add(n.asText()));
                boolean strict = c.path("strict").asBoolean(false);
                final String fl = lang;
                modes.put("baseline", () -> service.fileBaseline(fl, nbCar, lstCar, hints, strict));
                modes.put("indexed", () -> service.fileIndexed(fl, nbCar, lstCar, hints, strict));
                modes.put("split", () -> service.fileSplit(fl, nbCar, lstCar, hints, strict, degree));
            } else {
                String cars = c.path("cars").asText();
                final String fl = lang;
                modes.put("baseline", () -> service.manyBaseline(fl, cars, hints));
                modes.put("fanout", () -> service.manyFanout(fl, cars, hints));
                modes.put("nested", () -> service.manyNested(fl, cars, hints, degree));
            }

            Map<String, Object> modeJson = new LinkedHashMap<>();
            int count = 0;
            for (var e : modes.entrySet()) {
                int[] outCount = new int[1];
                Timing t = timeMode(e.getValue(), warmup, iters, outCount);
                count = outCount[0];
                modeJson.put(e.getKey(), Map.of("median_ms", t.medianMs(), "min_ms", t.minMs()));
                System.err.printf("[Java] %s / %s: %d words, median %.4f ms%n",
                        name, e.getKey(), count, t.medianMs());
            }
            Map<String, Object> caseOut = new LinkedHashMap<>();
            caseOut.put("name", name);
            caseOut.put("kind", kind);
            caseOut.put("count", count);
            caseOut.put("modes", modeJson);
            outCases.add(caseOut);
        }

        Map<String, Object> throughput = runThroughput(service);
        System.err.printf("[Java] throughput: %.1f ops/s @ concurrency %s%n",
                throughput.get("ops_per_sec"), throughput.get("concurrency"));

        Map<String, Object> report = new LinkedHashMap<>();
        report.put("language", "java");
        report.put("label", "Java");
        report.put("meta", Map.of("warmup", warmup, "iterations", iters, "split_degree", degree));
        report.put("cases", outCases);
        report.put("throughput", throughput);
        System.out.println(MAPPER.writeValueAsString(report));
    }
}
