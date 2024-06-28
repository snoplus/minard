const rackDropdown = document.getElementById("supply-rack");
const voltageDropdown = document.getElementById("supply-voltage");
const crateField = document.getElementById("baseline-crate");
const triggerDropdown = document.getElementById("baseline-trigger");
const flippyVoltage = document.getElementById("supply-flippy");
const MTCDVoltage = document.getElementById("mtcd");
const supplyRadio = document.getElementById("supply");
const baselineRadio = document.getElementById("baseline");
const appendPlotButton = document.getElementById("append-plot")
const newPlotButton = document.getElementById("new-plot")
const mismatchWarningText = document.getElementById("mismatch-warning")
const yMaxCheckbox = document.getElementById("y-max-check");
const yMinCheckbox = document.getElementById("y-min-check");
const yMaxValueEntry = document.getElementById("y-max-value");
const yMinValueEntry = document.getElementById("y-min-value");
const absoluteRadio = document.getElementById("y-axis-absolute");
const relativeRadio = document.getElementById("y-axis-relative");
const updateButton = document.getElementById("update-plot")

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
        appendPlotButton.removeAttribute("disabled");
        mismatchWarningText.style.visibility = "hidden";
    }
    else {
        appendPlotButton.setAttribute("disabled", "");
        mismatchWarningText.style.visibility = "";
    }
}

baselineRadio.onclick = function() {
    var currentMode = sessionStorage.getItem("dataType");
    if (currentMode == baselineRadio.id || currentMode == undefined) {
        appendPlotButton.removeAttribute("disabled");
        mismatchWarningText.style.visibility = "hidden";
    }
    else {
        appendPlotButton.setAttribute("disabled", "");
        mismatchWarningText.style.visibility = "";
    }
}