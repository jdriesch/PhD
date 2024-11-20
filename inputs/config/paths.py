import os

def get_paths(args):

    add_path = f'{args.version}/{args.year}'

    paths = {
        'datasets':f'inputs/config/datasets.json',
        'nanoAODs': f'inputs/nanoAODs/{args.year}.json',
        'plot_dir': f"results/plots/{add_path}/",
        'corr_dir': f"results/corrections/{add_path}/",
        'hist_dir': f"results/hists/{add_path}/",
        'condor_dir': f"results/condor/{add_path}/",
        'pu_json': f'inputs/jsonpog/POG/LUM/{args.year}/puWeights.json.gz',
        'snap_dir': f"/eos/user/j/jovonden/CMS_xycorr/snapshots/{add_path}/",
        'proxy_path': '/afs/cern.ch/user/j/jovonden/private/cert/x509up_u141674'
    }

    golden_jsons = {
        "2022_Summer22": "/eos/user/c/cmsdqm/www/CAF/certification/Collisions22/Cert_Collisions2022_355100_362760_Golden.json",
        "2022_Summer22EE": "/eos/user/c/cmsdqm/www/CAF/certification/Collisions22/Cert_Collisions2022_355100_362760_Golden.json"
    }

    for key in paths.keys():
        if 'dir' in key:
            os.makedirs(paths[key], exist_ok=True)

    paths['golden_json'] = golden_jsons[args.year]

    os.makedirs(paths['nanoAODs'].replace(paths['nanoAODs'].split('/')[-1], ''), exist_ok=True)

    return paths
