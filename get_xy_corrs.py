import ROOT
import argparse
import yaml
import json
import os
from tqdm  import tqdm
import tools.plot as plot

parser = argparse.ArgumentParser()
parser.add_argument(
    "-H", 
    "--hists", 
    action='store_true', 
    default=False,
    help='set to make 2d met vs npv histograms'
    )
parser.add_argument(
    "-C", 
    "--corr", 
    action='store_true', 
    default=False,
    help='set to get XY corrections'
    )
parser.add_argument(
    "-D", 
    "--datasets", 
    help="path to datasets; default is configs/datasets.yaml", 
    default='configs/datasets.yaml'
    )
parser.add_argument(
    "-S", 
    "--snapshot", 
    action='store_true', 
    default=False, 
    help="set if snapshot of data should be saved (for validation)"
    )
parser.add_argument(
    "-M",
    "--met",
    help="MET type; default is 'MET'",
    default='MET'
)


def filter_lumi(rdf, golden_json):
    """
    function to get rdf with events filtered with golden json
    
    (ROOT.RDataFrame) rdf: dataframe
    (str) golden_json: path to golden json
    """

    # load content of golden json
    with open(golden_json) as cf:
        goldenruns = json.load(cf)

    # extract runs and lumi sections to lists
    runs = [r for r in goldenruns.keys()]
    lumlist = [goldenruns[r] for r in goldenruns.keys()]

    # make c++ vectors of runlist and lumilist for dataframe
    runstr = "{" + ",".join(runs) + "}"
    lumstr = str(lumlist).replace("[", "{").replace("]", "}")

    # define quantity isGolden that is true iff it matches the lumi criteria
    rdf = rdf.Define(
        "isGolden",
        f"std::vector<int> runs = {runstr};"\
        f"std::vector<std::vector<std::vector<int>>> lums = {lumstr};"\
        """
            int index = -1;
            auto runidx = std::find(runs.begin(), runs.end(), run);
            if (runidx != runs.end()){
                index = runidx - runs.begin();
            }

            if (index == -1) {
                return 0;
            }

            int lumsecs = lums[index].size();
            for (int i=0; i<lumsecs; i++) {
                if (luminosityBlock >= lums[index][i][0] && luminosityBlock <= lums[index][i][1]){
                    return 1;
                }
            }

            return 0;
        """
    )
    return rdf.Filter("isGolden==1")

def makehists(infiles, hfile, hbins, golden_json, isdata, snap):
    """
    function to make 2d histograms for xy correction

    (list) infiles: list with event root files
    (str) hfile: name of output root file with histograms
    (dict) hbins: names of npv and met with histogram bins
    (str) golden_json: path to golden json
    (bool) isdata: True if data
    (str) snap: path to snapshot if snapshot should be stored; else: False
    """

    # create path to root output file and create file
    path = hfile.replace(hfile.split('/')[-1], '')
    os.makedirs(path, exist_ok=True)
    hfile = ROOT.TFile(hfile, "RECREATE")

    met, npv = hbins.keys()
    
    hists = {met+"_x": False, met+"_y": False}

    for f in tqdm(infiles):
        rdf = ROOT.RDataFrame("Events", f)


        if isdata:
            rdf = filter_lumi(rdf, golden_json)
            # print("data filtered using golden lumi json: ", golden_json)

        # definition of x and y component of met
        rdf = rdf.Define(f"{met}_x", f"{met}_pt*cos({met}_phi)")
        rdf = rdf.Define(f"{met}_y", f"{met}_pt*sin({met}_phi)")

        if snap:
            spath = f"{snap}{met}_{infiles.index(f)}.root"
            os.makedirs(snap, exist_ok=True)
            quants = [f'{met}_x', f'{met}_y', npv]
            rdf.Snapshot("Events", spath, quants)

        # definition of 2d histograms met_xy vs npv
        for var in hists.keys():
            h = rdf.Histo2D(
                (
                    var, 
                    var, 
                    hbins[npv][2], 
                    hbins[npv][0], 
                    hbins[npv][1], 
                    hbins[met][2], 
                    hbins[met][0], 
                    hbins[met][1]
                ),
                npv, var
            )

            if hists[var]:
                hists[var].Add(h.GetPtr())
            else:
                hists[var]=h
        
        for var in hists.keys():
            hists[var].Write()

    hfile.Close()

    return


def get_corrections(hfile, hbins, corr_file, tag, plots):
    """
    function to get xy corrections and plot results

    (str) hfile: name of root file with histograms
    (dict) hbins: names of npv and met with histogram bins
    (str) corr_file: name of correction file
    (bool) isdata: True or False
    (str) plots: path to plots
    """

    met, npv = hbins.keys()

    corr_dict = {}
    for xy in ['_x', '_y']:

        # read histograms from root file
        tf = ROOT.TFile(hfile, "READ")
        h = tf.Get(met+xy)
        h.SetDirectory(ROOT.nullptr)
        tf.Close()

        # define and fit pol1 function
        f1 = ROOT.TF1("pol1", "[0]*x+[1]", -10, 110)
        h.Fit(f1, "R", "", 0, 100)

        # save fit parameter
        corr_dict[xy] = {
            "m": f1.GetParameter(0),
            "c": f1.GetParameter(1)
        }

        # plot fit results
        plot.plot_2dim(
            h,
            title=tag,
            axis=['NPV', f'{met}{xy} (GeV)'],
            outfile=f"{plots}{met+xy}",
            xrange=[0,100],
            yrange=[hbins[met][0], hbins[met][1]],
            lumi='2022, 13.6 TeV',
            line=f1,
            results=[round(corr_dict[xy]["m"],3), round(corr_dict[xy]["c"],3)]
        )

    os.makedirs(corr_file, exist_ok=True)
    with open(f"{corr_file}{met}.yaml", "w") as f:
        yaml.dump(corr_dict, f)
            
    return


if __name__=='__main__':
    args = parser.parse_args()
    datasets = args.datasets
    met = args.met

    # load datasets
    with open(datasets, "r") as f:
        dsets = yaml.load(f, Loader=yaml.Loader)

    # define histogram bins
    hbins = {
        met: [-200, 200, 200],
        'PV_npvsGood': [0, 100, 100]
    }

    # go through runs / mc
    for tag in dsets.keys():
        
        # define output paths
        hists = f"results/hists/{tag}/{met}.root"
        corr_files = f"results/corrections/{tag}/"
        plots = f"results/plots/{tag}/"
        if args.snapshot:
            snaps = f"results/snapshots/{tag}/"
        else:
            snaps = False
            
        # get lists of process root files
        with open(f'configs/data/{tag}.yaml') as f:
            files = yaml.load(f, Loader=yaml.Loader)
        
        # make list of root files of the sample
        rootfiles = []
        for n in dsets[tag]["names"]:
            rootfiles += files[n]

        isdata = (dsets[tag]["type"]=="data")
        golden_json = dsets[tag]["gjson"]
    
        if args.hists:
            if os.path.exists(hists):
                ow = input(f"File {hists} already exists. Overwrite? (y/n)")
                if ow!="y":
                    print("File will not be overwritten.")
                    continue
            
            makehists(rootfiles, hists, hbins, golden_json, isdata, snaps)

        if args.corr:
            get_corrections(hists, hbins, corr_files, tag, plots)

