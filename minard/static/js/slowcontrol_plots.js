const rackDropdown = document.getElementById("supply-rack");
const voltageDropdown = document.getElementById("supply-voltage");
const crateField = document.getElementById("baseline-crate");
const triggerDropdown = document.getElementById("baseline-trigger");
const flippyVoltage = document.getElementById("supply-flippy");
const MTCDVoltage = document.getElementById("mtcd");
const defaultVoltage = document.getElementById("default-voltage");
const supplyRadio = document.getElementById("supply");
const baselineRadio = document.getElementById("baseline");
const metadataTable = document.getElementById("datastreams-listing")
const newPlotButton = document.getElementById("new-plot")
const appendPlotButton = document.getElementById("append-plot")
const mismatchWarningText = document.getElementById("mismatch-warning")

rackDropdown.onchange = function() {
    supplyRadio.checked = true;
    if (rackDropdown.value == "timing") {
        flippyVoltage.value = "6";
        flippyVoltage.innerHTML = "6V"
        MTCDVoltage.removeAttribute("hidden")
    }
    else {
        flippyVoltage.value = "8";
        flippyVoltage.innerHTML = "8V"
        if (voltageDropdown.value == "mtcd") {
            voltageDropdown.selectedIndex = 0;
        }
        MTCDVoltage.setAttribute("hidden", "")
    }
}

voltageDropdown.onchange = function() {
    supplyRadio.checked = true;
}

crateField.onchange = function() {
    baselineRadio.checked = true;
}

triggerDropdown.onchange = function() {
    baselineRadio.checked = true;
}

supplyRadio.onclick = function() {
    var currentMode = sessionStorage.getItem("dataType");
    if (currentMode == supplyRadio.id || currentMode == undefined) {
        //newPlotButton.removeAttribute("disabled");
        appendPlotButton.removeAttribute("disabled");
        mismatchWarningText.setAttribute("hidden", "");
    }
    else {
        //newPlotButton.setAttribute("disabled", "");
        appendPlotButton.setAttribute("disabled", "");
        mismatchWarningText.removeAttribute("hidden");
    }
}

baselineRadio.onclick = function() {
    var currentMode = sessionStorage.getItem("dataType");
    if (currentMode == baselineRadio.id || currentMode == undefined) {
        //newPlotButton.removeAttribute("disabled");
        appendPlotButton.removeAttribute("disabled");
        mismatchWarningText.setAttribute("hidden", "");
    }
    else {
        //newPlotButton.setAttribute("disabled", "");
        appendPlotButton.setAttribute("disabled", "");
        mismatchWarningText.removeAttribute("hidden")
    }
}
