from urllib.parse import urlparse, parse_qs, unquote_plus
import argparse, sys
def parse_appsheet_url(url: str):
    parsed = urlparse(url if (url.startswith('audiofarm://') or url.startswith('http')) else 'audiofarm://start?'+url)
    q = parse_qs(parsed.query)
    g=lambda k: unquote_plus(q.get(k,[""])[0])
    return {'patient_id':g('pid'),'full_name':g('nome'),'date_of_birth':g('dob'),'note':g('note'),'operator':g('op')}
def parse_cli_or_url(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv)==1 and (argv[0].startswith('audiofarm://') or argv[0].startswith('http') or 'pid=' in argv[0]):
        return parse_appsheet_url(argv[0])
    p=argparse.ArgumentParser(); p.add_argument('--pid',default=''); p.add_argument('--nome',default=''); p.add_argument('--dob',default=''); p.add_argument('--note',default=''); p.add_argument('--op',default='')
    return vars(p.parse_args(argv))
