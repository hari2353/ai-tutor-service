# MVCC vs Locking, Isolation Levels, Every Anomaly, Write Skew

> Sprint weekend 7 · source: `curriculum/17-databases/03-mvcc-isolation.md`

```
XMIN/XMAX      xmin = creating txn, xmax = deleting/superseding txn (0/null = live)
               VISIBLE if: xmin committed before snapshot AND
                           (xmax unset OR xmax's txn not committed before snapshot)
               Read Committed: new snapshot PER STATEMENT
               Repeatable Read/Serializable: ONE snapshot for whole transaction

2PL            shared lock on read, exclusive on write, held til commit;
               needs PREDICATE locks (not just row locks) to stop phantoms;
               readers block writers and vice versa -- the cost MVCC avoids

ANOMALIES      dirty read      - see uncommitted write
               dirty write     - overwrite uncommitted write
               read skew       - same row, 2 reads in 1 txn, different answers
               phantom         - predicate result set changes mid-txn
               lost update     - same row r-m-w, one write clobbers the other
               write skew      - DIFFERENT rows, disjoint writes jointly break
                                 an invariant neither write alone violated

LEVEL -> ANOMALY TABLE
  Read Uncommitted: all possible except dirty write
  Read Committed:   dirty read/write prevented; read skew/phantom/lost update/
                    write skew still possible
  Repeatable Read (ANSI min / MySQL): + read skew prevented; phantom/write
                    skew possible (MySQL's gap locks suppress most phantoms
                    beyond the ANSI minimum, in practice)
  Snapshot Isolation (Postgres REPEATABLE READ): + phantom + lost update
                    prevented (first-committer-wins); WRITE SKEW STILL POSSIBLE
  Serializable:     everything prevented (Postgres: SSI: Postgres: SSI, not
                    locking; MySQL/Oracle/SQLServer: locking-based)

DEFAULTS       Postgres/Oracle/SQL Server -> READ COMMITTED
               MySQL/InnoDB               -> REPEATABLE READ
               GOTCHA: Oracle "SERIALIZABLE" = snapshot isolation, NOT true
               serializable -- write skew still possible on Oracle SERIALIZABLE

SSI            SIREAD locks = bookkeeping only, never block · rw-antidependency
               = txn A reads what txn B later overwrites · dangerous structure =
               cycle of 2 rw-antidependencies through a pivot txn -> abort+retry

FIX WRITE SKEW SELECT ... FOR UPDATE on the invariant-backing rows (targeted,
               cheap) OR atomic conditional UPDATE ... WHERE cond (best for
               simple capacity checks) OR run at SERIALIZABLE (general, costs
               retry rate + SIREAD overhead across the whole txn)
```
