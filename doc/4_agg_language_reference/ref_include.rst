answer              	::= agg_out
                    	 | port_out
                    	 | distortion_out
                    	 | expr

distortion_out      	::= DISTORTION name ID expr
                    	 | DISTORTION name ID expr "[" numberl "]"

port_out            	::= PORT name note agg_list

agg_list            	::= agg_list agg_out
                    	 | agg_out

agg_out             	::= AGG name exposures layers sev_clause occ_reins freq agg_reins note
                    	 | AGG name dfreq layers sev_clause occ_reins agg_reins note
                    	 | AGG name TWEEDIE expr expr expr note
                    	 | AGG name builtin_agg agg_reins note
                    	 | builtin_agg agg_reins note

sev_out             	::= SEV name sev note
                    	 | SEV name dsev note

freq                	::= freq ZM expr
                    	 | freq ZT
                    	 | MIXED ID expr expr
                    	 | MIXED ID expr
                    	 | FREQ expr expr
                    	 | FREQ expr
                    	 | FREQ

agg_reins           	::= AGGREGATE NET OF reins_list
                    	 | AGGREGATE CEDED TO reins_list
                    	 |  %prec LOW

occ_reins           	::= OCCURRENCE NET OF reins_list
                    	 | OCCURRENCE CEDED TO reins_list
                    	 | 

reins_list          	::= reins_list AND reins_clause
                    	 | reins_clause
                    	 | tower

reins_clause        	::= expr XS expr
                    	 | expr SHARE_OF expr XS expr
                    	 | expr PART_OF expr XS expr

sev_clause          	::= SEV sev %prec LOW
                    	 | dsev
                    	 | BUILTIN_SEV

sev                 	::= sev picks
                    	 | sev "!"
                    	 | sev PLUS numbers
                    	 | sev MINUS numbers
                    	 | numbers TIMES sev
                    	 | ids numbers CV numbers weights
                    	 | ids numbers numbers weights
                    	 | ids numbers weights
                    	 | ids xps
                    	 | ids
                    	 | BUILTIN_SEV

xps                 	::= XPS doutcomes dprobs

dsev                	::= DSEV doutcomes dprobs

dfreq               	::= DFREQ doutcomes dprobs

picks               	::= PICKS "[" numberl "]" "[" numberl "]"

doutcomes           	::= "[" numberl "]"
                    	 | "[" expr RANGE expr "]"
                    	 | "[" expr RANGE expr RANGE expr "]"

dprobs              	::= "[" numberl "]"
                    	 | 

weights             	::= WEIGHTS EQUAL_WEIGHT expr
                    	 | WEIGHTS "[" numberl "]"
                    	 | 

layers              	::= numbers XS numbers
                    	 | tower
                    	 | 

tower               	::= TOWER doutcomes

note                	::= NOTE
                    	 |  %prec LOW

exposures           	::= numbers CLAIMS
                    	 | numbers LOSS
                    	 | numbers PREMIUM AT numbers LR
                    	 | numbers EXPOSURE AT numbers RATE

ids                 	::= "[" idl "]"
                    	 | ID

idl                 	::= idl ID
                    	 | ID

builtin_agg         	::= expr INHOMOG_MULTIPLY builtin_agg
                    	 | expr TIMES builtin_agg
                    	 | builtin_agg PLUS expr
                    	 | builtin_agg MINUS expr
                    	 | BUILTIN_AGG

name                	::= ID

numbers             	::= "[" numberl "]"
                    	 | expr

numberl             	::= numberl expr
                    	 | expr

expr                	::= term

term                	::= term DIVIDE factor
                    	 | factor

factor              	::= power
                    	 | "(" term ")"
                    	 | EXP "(" term ")"

power               	::= atom EXPONENT factor
                    	 | atom

atom                	::= NUMBER PERCENT
                    	 | INFINITY
                    	 | NUMBER

FREQ                    ::= 'binomial|poisson|bernoulli|pascal|geometric|neymana?|fixed'

BUILTINID               ::= 'sev|agg|port|meta.ID'

NOTE                    ::= 'note{TEXT}'

EQUAL_WEIGHT            ::= "="

AGG                     ::= 'agg'

AGGREGATE               ::= 'aggregate'

AND                     ::= 'and'

AT                      ::= 'at'

CEDED                   ::= 'ceded'

CLAIMS                  ::= 'claims|claim'

CONSTANT                ::= 'constant'

CV                      ::= 'cv'

DFREQ                   ::= 'dfreq'

DSEV                    ::= 'dsev'

EXP                     ::= 'exp'

EXPONENT                ::= '^|**'

INHOMOG_MULTIPLY        ::= "@"

INFINITY                ::= 'inf|unlim|unlimited'

LOSS                    ::= 'loss'

LR                      ::= 'lr'

MIXED                   ::= 'mixed'

NET                     ::= 'net'

OCCURRENCE              ::= 'occurrence'

OF                      ::= 'of'

PART_OF                 ::= 'po'

PERCENT                 ::= '%'

PORT                    ::= 'port'

PREMIUM                 ::= 'premium|prem'

SEV                     ::= 'sev'

SHARE_OF                ::= 'so'

TO                      ::= 'to'

WEIGHTS                 ::= 'wts|wt'

XPS                     ::= 'xps'

XS                      ::= "xs|x"

