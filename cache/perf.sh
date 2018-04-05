for s in 10 50 100 250 500 1000 1500 2000 2500 3000
do
  for m in 1 2
  do
    echo "s = $s; m = $m"
    perf stat -e L1-dcache-loads,L1-dcache-load-misses,LLC-loads,LLC-loads-misses,cache-references,cache-misses,dTLB-loads,dTLB-loads-misses,cpu-cycles,instructions java -jar cpumemory.jar $s $m 2> "s${s}m${m}.perf"
  done
done

echo "scenario" > perf.final
cat perf.out/s3000m1.perf | grep '(' | awk '{print $2}' >> perf.final
rm -rf perf.res
mkdir perf.res
for s in 10 50 100 250 500 1000 1500 2000 2500 3000
do
  for m in 1 2
  do
    basename="s${s}m${m}.perf"
    filename="perf.out/$basename"
    echo $filename
    echo "s${s}_m${m}" > "perf.res/$basename"
    cat $filename | grep '(' | awk '{print $1}' >> "perf.res/$basename"
    paste -d';' perf.final "perf.res/$basename" > perf.final.tmp
    mv perf.final.tmp perf.final
  done
done
