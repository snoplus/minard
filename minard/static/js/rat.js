function createPlotDiv(name){
    if (!document.getElementById(name)){
        var row = document.createElement(div);
        row.className = "row";

        var col = document.createElement("div");
        col.className = "col-md-8 col-md-offset-2";

        var div = document.createElement("div");
        div.id = name;
        div.className = "plot";

        col.appendChild(div);
        row.appendChild(col);
        document.body.appendChild(row);
    }
}

function displayRun(runNumber){
    var histFileName = $SCRIPT_ROOT + "/rat/r" + runNumber.toString() + "_nl_th1f.root";
    var ntupFileName = $SCRIPT_ROOT + "/rat/r" + runNumber.toString() + "_nl_ntups.zip";
    document.getElementById("histbut").onclick = function(){window.open(histFileName);};
    document.getElementById("ntupbut").onclick = function(){window.open(ntupFileName);};

    // open file
    new JSROOT.TFile(histFileName, function(file){
            // read the keys inside
            var plotNames = [];
            var keyNames = [];
            file.fKeys.forEach(function(key){keyNames.push(key.fName);});
            keyNames.sort();
            for(var k in keyNames){
                var keyName = keyNames[k];
                if(keyName === "StreamerInfo")
                    continue;
                plotNames.push(keyName);
            }

            // plot each in its own div
            for (var iDiv in plotNames){
                var plotName  = plotNames[iDiv];
                var divName   = plotName.replace(";", "_");
                createPlotDiv(divName);
                file.ReadObject(plotName, function(obj) {
                        JSROOT.draw(divName, obj, "E");
                        JSROOT.draw(divName, obj, "HISTF");
                    });
            }
    });
}