package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"sync/atomic"
	"time"
)

type LatencySummary struct {
	Min   float64 `json:"min"`
	Mean  float64 `json:"mean"`
	Stdev float64 `json:"stdev"`
	P50   float64 `json:"p50"`
	P90   float64 `json:"p90"`
	P95   float64 `json:"p95"`
	P99   float64 `json:"p99"`
	Max   float64 `json:"max"`
}

type ConcurrencyRunResult struct {
	Concurrency        int            `json:"concurrency"`
	WarmupSeconds      float64        `json:"warmup_s"`
	DurationSeconds    float64        `json:"duration_s"`
	LeaderName         string         `json:"leader_name"`
	LeaderURL          string         `json:"leader_url"`
	CompletedWrites    int            `json:"completed_writes"`
	Errors             uint64         `json:"errors"`
	ThroughputWPS      float64        `json:"throughput_wps"`
	LatencyMS          LatencySummary `json:"latency_ms"`
	FinalLogBytes      int64          `json:"final_log_bytes"`
	SnapshotsDuringRun int            `json:"snapshots_during_run"`
}

type WriteSample struct {
	WriteSeq   int     `json:"write_seq"`
	RaftIndex  uint64  `json:"raft_index"`
	StartMS    float64 `json:"start_ms"`
	ElapsedMS  float64 `json:"elapsed_ms"`
	LatencyMS  float64 `json:"latency_ms"`
}

type DiskSample struct {
	ElapsedMS           float64 `json:"elapsed_ms"`
	CompletedWrites     uint64  `json:"completed_writes"`
	LastRaftIndex       uint64  `json:"last_raft_index"`
	LogBytes            int64   `json:"log_bytes"`
	LogNewExists        bool    `json:"log_new_exists"`
	SnapshotCount       int     `json:"snapshot_count"`
	LatestSnapshot      string  `json:"latest_snapshot,omitempty"`
	LatestSnapshotBytes int64   `json:"latest_snapshot_bytes,omitempty"`
}

type SnapshotEvent struct {
	Node            string  `json:"node"`
	Filename        string  `json:"filename"`
	Bytes           int64   `json:"bytes"`
	DetectedAtMS    float64 `json:"detected_at_ms"`
	CompletedWrites uint64  `json:"completed_writes"`
	LastRaftIndex   uint64  `json:"last_raft_index"`
}

type CompactionRunResult struct {
	Concurrency           int             `json:"concurrency"`
	TotalWrites           int             `json:"total_writes"`
	RateLimitWPS          int             `json:"rate_limit_wps"`
	LeaderName            string          `json:"leader_name"`
	LeaderURL             string          `json:"leader_url"`
	DurationSeconds       float64         `json:"duration_s"`
	ThroughputWPS         float64         `json:"throughput_wps"`
	Errors                uint64          `json:"errors"`
	OverallLatencyMS      LatencySummary  `json:"overall_latency_ms"`
	SteadyPreCompactMS    LatencySummary  `json:"steady_pre_compact_latency_ms"`
	PeakLatencyMS         float64         `json:"peak_latency_ms"`
	PeakLogBytes          int64           `json:"peak_log_bytes"`
	PostCompactMinBytes   int64           `json:"post_compact_min_log_bytes"`
	CompactionWriteSeq    uint64          `json:"compaction_write_seq"`
	CompactionElapsedMS   float64         `json:"compaction_elapsed_ms"`
	SnapshotEvents        []SnapshotEvent `json:"snapshot_events"`
	DiskSamples           []DiskSample    `json:"disk_samples"`
	Writes                []WriteSample   `json:"writes"`
}

type leaderStatsResp struct {
	Leader    string                 `json:"leader"`
	Followers map[string]interface{} `json:"followers"`
}

func newHTTPClient() *http.Client {
	transport := &http.Transport{
		MaxIdleConns:        1024,
		MaxIdleConnsPerHost: 512,
		MaxConnsPerHost:     0,
		IdleConnTimeout:     90 * time.Second,
		DisableCompression:  true,
	}
	return &http.Client{
		Transport: transport,
		Timeout:   30 * time.Second,
		CheckRedirect: func(req *http.Request, via []*http.Request) error {
			return http.ErrUseLastResponse
		},
	}
}

func buildPayloads(count int, valueSize int) [][]byte {
	const alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	payloads := make([][]byte, count)
	for i := 0; i < count; i++ {
		val := make([]byte, valueSize)
		prefix := fmt.Sprintf("v%04d-", i)
		copy(val, prefix)
		for j := len(prefix); j < valueSize; j++ {
			val[j] = alphabet[(i*31+j*17)%len(alphabet)]
		}
		payloads[i] = []byte("value=" + string(val))
	}
	return payloads
}

func buildKeyURLs(leaderURL string, keySpace int) []string {
	urls := make([]string, keySpace)
	base := strings.TrimRight(leaderURL, "/")
	for i := 0; i < keySpace; i++ {
		urls[i] = fmt.Sprintf("%s/v2/keys/bench/key-%d", base, i)
	}
	return urls
}

func hostFromURL(rawURL string) string {
	u, err := url.Parse(rawURL)
	if err != nil {
		return rawURL
	}
	host := u.Host
	if idx := strings.IndexByte(host, ':'); idx >= 0 {
		return host[:idx]
	}
	return host
}

func discoverLeader(client *http.Client, endpoints []string, expectedMembers int, probePayload []byte) (string, string, error) {
	deadline := time.Now().Add(45 * time.Second)
	for time.Now().Before(deadline) {
		allUp := true
		for _, ep := range endpoints {
			resp, err := client.Get(strings.TrimRight(ep, "/") + "/version")
			if err != nil {
				allUp = false
				break
			}
			_, _ = io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
			if resp.StatusCode != http.StatusOK {
				allUp = false
				break
			}
		}
		if !allUp {
			time.Sleep(150 * time.Millisecond)
			continue
		}

		// Verify all cluster members are registered.
		mResp, err := client.Get(strings.TrimRight(endpoints[0], "/") + "/v2/machines")
		if err != nil {
			time.Sleep(150 * time.Millisecond)
			continue
		}
		mBody, _ := io.ReadAll(mResp.Body)
		mResp.Body.Close()
		if mResp.StatusCode != http.StatusOK {
			time.Sleep(150 * time.Millisecond)
			continue
		}
		parts := strings.Split(string(mBody), ",")
		memberCount := 0
		for _, p := range parts {
			if strings.TrimSpace(p) != "" {
				memberCount++
			}
		}
		if memberCount < expectedMembers {
			time.Sleep(150 * time.Millisecond)
			continue
		}

		// Query /v2/stats/leader on every endpoint to find the active Raft leader.
		for _, ep := range endpoints {
			lResp, err := client.Get(strings.TrimRight(ep, "/") + "/v2/stats/leader")
			if err != nil {
				continue
			}
			lBody, _ := io.ReadAll(lResp.Body)
			lResp.Body.Close()
			if lResp.StatusCode != http.StatusOK {
				continue
			}
			var ls leaderStatsResp
			if err := json.Unmarshal(lBody, &ls); err != nil {
				continue
			}
			if len(ls.Followers) < expectedMembers-1 {
				continue
			}

			// Verify 5 direct probe writes succeed without redirect.
			probeOK := true
			probeURL := strings.TrimRight(ep, "/") + "/v2/keys/bench/_probe"
			for p := 0; p < 5; p++ {
				req, err := http.NewRequest(http.MethodPut, probeURL, bytes.NewReader(probePayload))
				if err != nil {
					probeOK = false
					break
				}
				req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
				wResp, err := client.Do(req)
				if err != nil {
					probeOK = false
					break
				}
				_, _ = io.Copy(io.Discard, wResp.Body)
				wResp.Body.Close()
				if wResp.StatusCode != http.StatusOK && wResp.StatusCode != http.StatusCreated {
					probeOK = false
					break
				}
			}
			if probeOK {
				time.Sleep(200 * time.Millisecond)
				return hostFromURL(ep), strings.TrimRight(ep, "/"), nil
			}
		}

		time.Sleep(150 * time.Millisecond)
	}
	return "", "", fmt.Errorf("timed out waiting for %d-node cluster readiness and leader election", expectedMembers)
}

func doPut(client *http.Client, targetURL string, body []byte) (uint64, error) {
	req, err := http.NewRequest(http.MethodPut, targetURL, bytes.NewReader(body))
	if err != nil {
		return 0, err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	resp, err := client.Do(req)
	if err != nil {
		return 0, err
	}
	_, _ = io.Copy(io.Discard, resp.Body)
	resp.Body.Close()
	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		return 0, fmt.Errorf("unexpected HTTP status %d", resp.StatusCode)
	}
	var raftIdx uint64
	if hdr := resp.Header.Get("X-Raft-Index"); hdr != "" {
		raftIdx, _ = strconv.ParseUint(hdr, 10, 64)
	} else if hdr := resp.Header.Get("X-Etcd-Index"); hdr != "" {
		raftIdx, _ = strconv.ParseUint(hdr, 10, 64)
	}
	return raftIdx, nil
}

type dirDiskState struct {
	logBytes            int64
	logNewExists        bool
	snapFiles           map[string]int64
	latestSnapshot      string
	latestSnapshotBytes int64
}

func inspectDataDir(mountPath string) dirDiskState {
	st := dirDiskState{
		snapFiles: make(map[string]int64),
	}
	v2WalDir := filepath.Join(mountPath, "member", "wal")
	if entries, err := os.ReadDir(v2WalDir); err == nil {
		for _, e := range entries {
			if !e.IsDir() && strings.HasSuffix(e.Name(), ".wal") {
				if info, err := e.Info(); err == nil {
					st.logBytes += info.Size()
				}
			}
		}
		v2SnapDir := filepath.Join(mountPath, "member", "snap")
		if sEntries, err := os.ReadDir(v2SnapDir); err == nil {
			var names []string
			for _, e := range sEntries {
				if !e.IsDir() && strings.HasSuffix(e.Name(), ".snap") {
					if info, err := e.Info(); err == nil {
						st.snapFiles[e.Name()] = info.Size()
						names = append(names, e.Name())
					}
				}
			}
			sort.Strings(names)
			if len(names) > 0 {
				st.latestSnapshot = names[len(names)-1]
				st.latestSnapshotBytes = st.snapFiles[st.latestSnapshot]
			}
		}
		return st
	}

	// etcd v0.4.x layout: /var/lib/etcd/log, /var/lib/etcd/log.new, /var/lib/etcd/snapshot/*.ss
	if info, err := os.Stat(filepath.Join(mountPath, "log")); err == nil {
		st.logBytes = info.Size()
	}
	if _, err := os.Stat(filepath.Join(mountPath, "log.new")); err == nil {
		st.logNewExists = true
	}
	snapDir := filepath.Join(mountPath, "snapshot")
	if sEntries, err := os.ReadDir(snapDir); err == nil {
		var latestMod time.Time
		for _, e := range sEntries {
			if !e.IsDir() && strings.HasSuffix(e.Name(), ".ss") {
				if info, err := e.Info(); err == nil {
					st.snapFiles[e.Name()] = info.Size()
					if st.latestSnapshot == "" || info.ModTime().After(latestMod) || (info.ModTime().Equal(latestMod) && e.Name() > st.latestSnapshot) {
						latestMod = info.ModTime()
						st.latestSnapshot = e.Name()
						st.latestSnapshotBytes = info.Size()
					}
				}
			}
		}
	}
	return st
}

func summarizeLatencies(vals []float64) LatencySummary {
	if len(vals) == 0 {
		return LatencySummary{}
	}
	sorted := make([]float64, len(vals))
	copy(sorted, vals)
	sort.Float64s(sorted)

	var sum float64
	for _, v := range sorted {
		sum += v
	}
	mean := sum / float64(len(sorted))

	var sqDiff float64
	for _, v := range sorted {
		d := v - mean
		sqDiff += d * d
	}
	stdev := math.Sqrt(sqDiff / float64(len(sorted)))

	pct := func(p float64) float64 {
		if len(sorted) == 1 {
			return sorted[0]
		}
		pos := p * float64(len(sorted)-1)
		lo := int(math.Floor(pos))
		hi := int(math.Ceil(pos))
		if lo == hi {
			return sorted[lo]
		}
		frac := pos - float64(lo)
		return sorted[lo]*(1.0-frac) + sorted[hi]*frac
	}

	return LatencySummary{
		Min:   round3(sorted[0]),
		Mean:  round3(mean),
		Stdev: round3(stdev),
		P50:   round3(pct(0.50)),
		P90:   round3(pct(0.90)),
		P95:   round3(pct(0.95)),
		P99:   round3(pct(0.99)),
		Max:   round3(sorted[len(sorted)-1]),
	}
}

func round3(v float64) float64 {
	return math.Round(v*1000.0) / 1000.0
}

func runConcurrencyMode(
	client *http.Client,
	endpoints []string,
	dataMounts string,
	concurrency int,
	warmup time.Duration,
	duration time.Duration,
	keySpace int,
	valueSize int,
	outPath string,
) error {
	payloads := buildPayloads(keySpace, valueSize)
	leaderName, leaderURL, err := discoverLeader(client, endpoints, len(endpoints), payloads[0])
	if err != nil {
		return err
	}
	keyURLs := buildKeyURLs(leaderURL, keySpace)
	fmt.Printf("[concurrency c=%d] leader=%s (%s), warmup=%s, measure=%s\n",
		concurrency, leaderName, leaderURL, warmup, duration)

	workerLatencies := make([][]float64, concurrency)
	for i := range workerLatencies {
		workerLatencies[i] = make([]float64, 0, 16384)
	}

	var seq uint64
	var errCount uint64

	start := time.Now()
	measureStart := start.Add(warmup)
	measureEnd := measureStart.Add(duration)

	var wg sync.WaitGroup
	wg.Add(concurrency)
	for w := 0; w < concurrency; w++ {
		wIdx := w
		go func() {
			defer wg.Done()
			local := workerLatencies[wIdx]
			for {
				now := time.Now()
				if !now.Before(measureEnd) {
					break
				}
				k := atomic.AddUint64(&seq, 1)
				slot := int(k % uint64(keySpace))
				t0 := time.Now()
				_, err := doPut(client, keyURLs[slot], payloads[slot])
				t1 := time.Now()
				if err != nil {
					atomic.AddUint64(&errCount, 1)
					continue
				}
				if !t1.Before(measureStart) && !t1.After(measureEnd) {
					latMS := float64(t1.Sub(t0).Nanoseconds()) / 1e6
					local = append(local, latMS)
				}
			}
			workerLatencies[wIdx] = local
		}()
	}
	wg.Wait()

	var all []float64
	for _, wl := range workerLatencies {
		all = append(all, wl...)
	}

	leaderMount := filepath.Join(dataMounts, leaderName)
	diskAfter := inspectDataDir(leaderMount)

	summary := summarizeLatencies(all)
	tps := float64(len(all)) / duration.Seconds()

	res := ConcurrencyRunResult{
		Concurrency:        concurrency,
		WarmupSeconds:      warmup.Seconds(),
		DurationSeconds:    duration.Seconds(),
		LeaderName:         leaderName,
		LeaderURL:          leaderURL,
		CompletedWrites:    len(all),
		Errors:             errCount,
		ThroughputWPS:      round3(tps),
		LatencyMS:          summary,
		FinalLogBytes:      diskAfter.logBytes,
		SnapshotsDuringRun: len(diskAfter.snapFiles),
	}

	fmt.Printf("[concurrency c=%d] completed=%d writes (%.1f writes/s) p50=%.2fms p95=%.2fms p99=%.2fms max=%.2fms errors=%d snaps=%d\n",
		concurrency, res.CompletedWrites, res.ThroughputWPS,
		res.LatencyMS.P50, res.LatencyMS.P95, res.LatencyMS.P99, res.LatencyMS.Max,
		res.Errors, res.SnapshotsDuringRun)

	return writeJSON(outPath, res)
}

func runCompactionMode(
	client *http.Client,
	endpoints []string,
	dataMounts string,
	concurrency int,
	totalWrites int,
	rateLimit int,
	sampleInterval time.Duration,
	keySpace int,
	valueSize int,
	outPath string,
) error {
	payloads := buildPayloads(keySpace, valueSize)
	leaderName, leaderURL, err := discoverLeader(client, endpoints, len(endpoints), payloads[0])
	if err != nil {
		return err
	}
	keyURLs := buildKeyURLs(leaderURL, keySpace)
	fmt.Printf("[compaction] leader=%s (%s), c=%d, total_writes=%d, rate_limit=%d wps\n",
		leaderName, leaderURL, concurrency, totalWrites, rateLimit)

	// Warm persistent keep-alive connections (2 requests per worker) so TCP setup does not skew write #1.
	var warmWG sync.WaitGroup
	warmWG.Add(concurrency)
	for w := 0; w < concurrency; w++ {
		wIdx := w
		go func() {
			defer warmWG.Done()
			for i := 0; i < 2; i++ {
				slot := (wIdx*2 + i) % keySpace
				_, _ = doPut(client, keyURLs[slot], payloads[slot])
			}
		}()
	}
	warmWG.Wait()

	var minCycle time.Duration
	if rateLimit > 0 {
		minCycle = time.Duration(float64(concurrency) / float64(rateLimit) * float64(time.Second))
	}

	workerSamples := make([][]WriteSample, concurrency)
	perWorkerCap := (totalWrites / concurrency) + 64
	for i := range workerSamples {
		workerSamples[i] = make([]WriteSample, 0, perWorkerCap)
	}

	var dispatched uint64
	var completed uint64
	var latestRaftIdx uint64
	var errCount uint64

	nodeNames := make([]string, 0, len(endpoints))
	for _, ep := range endpoints {
		nodeNames = append(nodeNames, hostFromURL(ep))
	}
	leaderMount := filepath.Join(dataMounts, leaderName)

	phaseStart := time.Now()
	stopSampler := make(chan struct{})
	var samplerWG sync.WaitGroup
	var diskSamples []DiskSample
	var snapshotEvents []SnapshotEvent
	seenSnaps := make(map[string]int)

	recordDiskTick := func() {
		elapsedMS := float64(time.Since(phaseStart).Nanoseconds()) / 1e6
		comp := atomic.LoadUint64(&completed)
		rIdx := atomic.LoadUint64(&latestRaftIdx)

		st := inspectDataDir(leaderMount)
		diskSamples = append(diskSamples, DiskSample{
			ElapsedMS:           round3(elapsedMS),
			CompletedWrites:     comp,
			LastRaftIndex:       rIdx,
			LogBytes:            st.logBytes,
			LogNewExists:        st.logNewExists,
			SnapshotCount:       len(st.snapFiles),
			LatestSnapshot:      st.latestSnapshot,
			LatestSnapshotBytes: st.latestSnapshotBytes,
		})

		for _, n := range nodeNames {
			nst := inspectDataDir(filepath.Join(dataMounts, n))
			for fname, sz := range nst.snapFiles {
				key := n + ":" + fname
				if idx, ok := seenSnaps[key]; !ok {
					seenSnaps[key] = len(snapshotEvents)
					snapshotEvents = append(snapshotEvents, SnapshotEvent{
						Node:            n,
						Filename:        fname,
						Bytes:           sz,
						DetectedAtMS:    round3(elapsedMS),
						CompletedWrites: comp,
						LastRaftIndex:   rIdx,
					})
				} else if sz > snapshotEvents[idx].Bytes {
					snapshotEvents[idx].Bytes = sz
				}
			}
		}
	}

	recordDiskTick()
	samplerWG.Add(1)
	go func() {
		defer samplerWG.Done()
		ticker := time.NewTicker(sampleInterval)
		defer ticker.Stop()
		for {
			select {
			case <-stopSampler:
				return
			case <-ticker.C:
				recordDiskTick()
			}
		}
	}()

	var wg sync.WaitGroup
	wg.Add(concurrency)
	for w := 0; w < concurrency; w++ {
		wIdx := w
		go func() {
			defer wg.Done()
			local := workerSamples[wIdx]
			for {
				n := atomic.AddUint64(&dispatched, 1)
				if int(n) > totalWrites {
					break
				}
				slot := int(n % uint64(keySpace))
				t0 := time.Now()
				rIdx, err := doPut(client, keyURLs[slot], payloads[slot])
				t1 := time.Now()
				if err != nil {
					atomic.AddUint64(&errCount, 1)
					continue
				}
				atomic.AddUint64(&completed, 1)
				if rIdx > 0 {
					for {
						cur := atomic.LoadUint64(&latestRaftIdx)
						if rIdx <= cur || atomic.CompareAndSwapUint64(&latestRaftIdx, cur, rIdx) {
							break
						}
					}
				}
				startMS := float64(t0.Sub(phaseStart).Nanoseconds()) / 1e6
				endMS := float64(t1.Sub(phaseStart).Nanoseconds()) / 1e6
				latMS := float64(t1.Sub(t0).Nanoseconds()) / 1e6
				local = append(local, WriteSample{
					RaftIndex: rIdx,
					StartMS:   round3(startMS),
					ElapsedMS: round3(endMS),
					LatencyMS: round3(latMS),
				})

				if minCycle > 0 {
					reqDur := t1.Sub(t0)
					if reqDur < minCycle {
						time.Sleep(minCycle - reqDur)
					}
				}
			}
			workerSamples[wIdx] = local
		}()
	}
	wg.Wait()
	totalDur := time.Since(phaseStart)
	close(stopSampler)
	samplerWG.Wait()
	recordDiskTick()

	allWrites := make([]WriteSample, 0, totalWrites)
	for _, ws := range workerSamples {
		allWrites = append(allWrites, ws...)
	}
	sort.Slice(allWrites, func(i, j int) bool {
		if allWrites[i].ElapsedMS == allWrites[j].ElapsedMS {
			return allWrites[i].RaftIndex < allWrites[j].RaftIndex
		}
		return allWrites[i].ElapsedMS < allWrites[j].ElapsedMS
	})
	allLat := make([]float64, len(allWrites))
	var preCompactLat []float64
	for i := range allWrites {
		allWrites[i].WriteSeq = i + 1
		allLat[i] = allWrites[i].LatencyMS
		if i < 9500 && i >= 200 {
			preCompactLat = append(preCompactLat, allWrites[i].LatencyMS)
		}
	}

	var peakLog int64
	postCompactMin := int64(math.MaxInt64)
	var compactSeq uint64
	var compactElapsed float64
	for i, ds := range diskSamples {
		if ds.LogBytes > peakLog {
			peakLog = ds.LogBytes
		}
		if i > 0 && diskSamples[i-1].LogBytes > 1024*1024 && ds.LogBytes < diskSamples[i-1].LogBytes/2 {
			if compactSeq == 0 {
				compactSeq = ds.CompletedWrites
				compactElapsed = ds.ElapsedMS
			}
			if ds.LogBytes < postCompactMin {
				postCompactMin = ds.LogBytes
			}
		} else if compactSeq > 0 && ds.LogBytes < postCompactMin {
			postCompactMin = ds.LogBytes
		}
	}
	if postCompactMin == int64(math.MaxInt64) {
		postCompactMin = peakLog
	}

	overallSummary := summarizeLatencies(allLat)
	preSummary := summarizeLatencies(preCompactLat)

	res := CompactionRunResult{
		Concurrency:         concurrency,
		TotalWrites:         len(allWrites),
		RateLimitWPS:        rateLimit,
		LeaderName:          leaderName,
		LeaderURL:           leaderURL,
		DurationSeconds:     round3(totalDur.Seconds()),
		ThroughputWPS:       round3(float64(len(allWrites)) / totalDur.Seconds()),
		Errors:              errCount,
		OverallLatencyMS:    overallSummary,
		SteadyPreCompactMS:  preSummary,
		PeakLatencyMS:       overallSummary.Max,
		PeakLogBytes:        peakLog,
		PostCompactMinBytes: postCompactMin,
		CompactionWriteSeq:  compactSeq,
		CompactionElapsedMS: compactElapsed,
		SnapshotEvents:      snapshotEvents,
		DiskSamples:         diskSamples,
		Writes:              allWrites,
	}

	fmt.Printf("[compaction] completed=%d in %.2fs (%.1f writes/s), pre-compact p50=%.2fms p99=%.2fms, peak=%.2fms, log %.2fMB -> %.2fMB at seq=%d (t=%.2fs), snap_events=%d\n",
		res.TotalWrites, res.DurationSeconds, res.ThroughputWPS,
		res.SteadyPreCompactMS.P50, res.SteadyPreCompactMS.P99, res.PeakLatencyMS,
		float64(res.PeakLogBytes)/(1024*1024), float64(res.PostCompactMinBytes)/(1024*1024),
		res.CompactionWriteSeq, res.CompactionElapsedMS/1000.0, len(res.SnapshotEvents))

	return writeJSON(outPath, res)
}

func writeJSON(path string, v interface{}) error {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, b, 0644)
}

func main() {
	mode := flag.String("mode", "concurrency", "Benchmark mode: concurrency | compaction")
	endpointsStr := flag.String("endpoints", "http://etcd-1:4001,http://etcd-2:4001,http://etcd-3:4001", "Comma-separated etcd client URLs")
	dataMounts := flag.String("data-mounts", "/mnt", "Directory containing read-only mounts of etcd volumes (/mnt/etcd-1, ...)")
	concurrency := flag.Int("concurrency", 16, "Number of concurrent client workers")
	warmup := flag.Duration("warmup", 3*time.Second, "Warmup duration (concurrency mode)")
	duration := flag.Duration("duration", 15*time.Second, "Measurement window duration (concurrency mode)")
	totalWrites := flag.Int("total-writes", 20000, "Total measured writes (compaction mode)")
	rateLimit := flag.Int("rate-limit", 1400, "Aggregate write rate cap in writes/sec for compaction mode (0 = unlimited)")
	sampleInterval := flag.Duration("sample-interval", 100*time.Millisecond, "Leader disk sampling interval (compaction mode)")
	keySpace := flag.Int("key-space", 1000, "Number of distinct keys (/v2/keys/bench/key-<i % keySpace>)")
	valueSize := flag.Int("value-size", 256, "Deterministic payload size in bytes")
	outPath := flag.String("out", "/results/run.json", "Output JSON path")
	flag.Parse()

	endpoints := strings.Split(*endpointsStr, ",")
	for i := range endpoints {
		endpoints[i] = strings.TrimSpace(endpoints[i])
	}

	client := newHTTPClient()

	var err error
	switch *mode {
	case "concurrency":
		err = runConcurrencyMode(client, endpoints, *dataMounts, *concurrency, *warmup, *duration, *keySpace, *valueSize, *outPath)
	case "compaction":
		err = runCompactionMode(client, endpoints, *dataMounts, *concurrency, *totalWrites, *rateLimit, *sampleInterval, *keySpace, *valueSize, *outPath)
	default:
		err = fmt.Errorf("unknown --mode %q (expected concurrency or compaction)", *mode)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "benchmark failed: %v\n", err)
		os.Exit(1)
	}
}
