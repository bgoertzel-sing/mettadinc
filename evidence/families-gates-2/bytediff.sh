#!/bin/sh
# byte-diff: every tracked .metta of the gates-2 tree, both modes, HEAD 8fd2fec binary vs gates-2 binary
. /home/openclaw/scratch/mettadinc-proof-backend/env.sh
NEW=/home/openclaw/research-agent/projects/mettadinc/repos/wt-families-gates-2
OLD=/home/openclaw/research-agent/projects/mettadinc/repos/wt-fg2-baseline
O=/home/openclaw/scratch/fg2/bytediff; rm -rf $O; mkdir -p $O/old $O/new
cd $NEW
n=0; same=0; diff=0; onlynew=0
git ls-files '*.metta' > $O/files.txt
while read f; do
  for m in release beyond; do
    a=""; [ $m = beyond ] && a=--beyond-release
    k=$(echo "$f" | tr / _).$m
    timeout 600 $NEW/build/dcalc/dcalc $a "$NEW/$f" > $O/new/$k 2>&1; echo "exit $?" >> $O/new/$k
    n=$((n+1))
    if [ -f "$OLD/$f" ]; then
      timeout 600 $OLD/build/dcalc/dcalc $a "$OLD/$f" > $O/old/$k 2>&1; echo "exit $?" >> $O/old/$k
      # paths differ between trees; normalise the tree root
      sed -i "s#$OLD#ROOT#g" $O/old/$k; sed -i "s#$NEW#ROOT#g" $O/new/$k
      if cmp -s $O/old/$k $O/new/$k; then same=$((same+1)); else diff=$((diff+1)); echo "DIFF $f $m"; fi
    else onlynew=$((onlynew+1)); echo "NEW $f $m"; fi
  done
done < $O/files.txt
echo "bytediff: $(wc -l < $O/files.txt) tracked .metta, $n outputs: $same identical, $diff differ, $onlynew new-only"
