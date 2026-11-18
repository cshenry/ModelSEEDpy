# -*- coding: utf-8 -*-
"""HTML reports for FBA solutions, SteadyCom and CommScores results.

Each report function renders a Jinja2 template that ships beside this module
(``core/*.html``), writes it to ``export_html_path`` and returns the HTML.
"""
from itertools import zip_longest
from numpy import isnan, load
import jinja2
import os, re, math, json

package_dir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "..")
templates_dir = os.path.abspath(os.path.dirname(__file__))


def _render(template_name, content, export_html_path):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_dir),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )
    html_report = env.get_template(template_name).render(content)
    if export_html_path is not None:
        with open(export_html_path, "w", encoding="utf-8") as out:
            out.write(html_report)
    return html_report


# Helper function
def round_float_str(s, precision=6):
    """
    Given a string containing floats delimited by whitespace
    round each float in the string and return the rounded string.

    Parameters
    ----------
    s : str
        String containing floats
    precision : int
        Number of decimals to round each float to
    """
    round_str = ""
    for token in s.split():
        try:
            f = round(float(token), precision)
            round_str += str(f)
        except ValueError:
            round_str += token
        round_str += " "
    return round_str


# Helper functions for formating
missing_format = lambda x: x if x else "-"
nan_format = lambda x: "-" if isnan(x) else x
round_format = lambda x: nan_format(round(x, 6))
equation_format = lambda rxn: round_float_str(
    rxn.build_reaction_string(use_metabolite_names=True)
)
name_id_format = lambda obj: f"{obj.name or obj.id}\n({obj.id})"


# Helper function to determine reaction class
def class_formater(rxnID, fva_sol):
    min_zero = math.isclose(fva_sol.minimum[rxnID], 0, abs_tol=1e-07)
    max_zero = math.isclose(fva_sol.maximum[rxnID], 0, abs_tol=1e-07)

    min_ = 0 if min_zero else fva_sol.minimum[rxnID]
    max_ = 0 if max_zero else fva_sol.maximum[rxnID]

    if min_zero and max_zero:
        return "blocked"
    if min_ > 0 or max_ < 0:
        return "essential"
    # if min_ < 0 or max_ > 0:
    return "functional"


# Helper function to format reaction/ex-reaction display data
def reaction_formater(model, fba_sol, fva_sol, ex):
    """ex specifies exchange reaction"""
    if fva_sol is None:
        return json.dumps([])

    # Select either exchange or normal reactions
    if ex:
        rxnIDs = fva_sol.loc[fva_sol.index.str[:2] == "EX"].index
    else:
        rxnIDs = fva_sol.loc[fva_sol.index.str[:2] != "EX"].index

    # Get reaction objects from ids
    rxns = map(model.reactions.get_by_id, rxnIDs)

    return json.dumps(
        [
            {
                "id": rxnID,
                "flux": round_format(fba_sol.fluxes[rxnID]),
                "min_flux": round_format(fva_sol.minimum[rxnID]),
                "max_flux": round_format(fva_sol.maximum[rxnID]),
                "class": class_formater(rxnID, fva_sol),
                "equation": equation_format(rxn),
                "name": missing_format(rxn.name),
            }
            for rxnID, rxn in zip(rxnIDs, rxns)
        ]
    )


def _nonzero_rows(frame, tolerance):
    """The rows of a cobra summary flux table that carry flux, largest first."""
    frame = frame.loc[frame["flux"].abs() > tolerance]
    return frame.reindex(frame["flux"].abs().sort_values(ascending=False).index)


# Helper function for formatting model summary
def model_summary(model, fba_sol=None):
    """Rows of (uptake, flux, secretion, flux, objective, flux) for the
    summary table, from cobra's ModelSummary of ``fba_sol``."""
    from cobra.util.solver import linear_reaction_coefficients

    summary = model.summary(solution=fba_sol)
    uptake, secretion = [
        [
            (
                name_id_format(model.metabolites.get_by_id(row.metabolite)),
                round_format(row.flux),
            )
            for row in _nonzero_rows(frame, model.tolerance).itertuples()
        ]
        for frame in (summary.uptake_flux, summary.secretion_flux)
    ]
    fluxes = fba_sol.fluxes if fba_sol is not None else model.optimize().fluxes
    objectives = [
        (name_id_format(rxn), round_format(fluxes[rxn.id] * coef))
        for rxn, coef in linear_reaction_coefficients(model).items()
    ]
    return [
        [
            entry if entry is not None else "-"
            for column in row
            for entry in (column if column is not None else (None, None))
        ]
        for row in zip_longest(uptake, secretion, objectives)
    ]


# Helper function for formatting ATP summary
def atp_summary_formatter(model, fba_sol=None):
    """Returns list of ATP summary values if metabolites are found
    or a message stating they could not be found. Also return a
    bool specicifying whether or not summary exists."""

    # Select ATP metabolite
    for atp_id in ("atp_c", "ATP_c", "cpd00002_c0"):
        if atp_id in model.metabolites:
            summary = model.metabolites.get_by_id(atp_id).summary(solution=fba_sol)
            break
    else:
        # Empty ATP summary
        msg = (
            "None of the < atp_c, ATP_c, and cpd00002_c0 > metabolites are defined. "
            "Add one of these metabolites in the model to display an ATP summary."
        )
        return msg, False

    atp_summary = []
    for side, frame in (
        ("PRODUCING", summary.producing_flux),
        ("CONSUMING", summary.consuming_flux),
    ):
        for row in _nonzero_rows(frame, model.tolerance).itertuples():
            rxn = model.reactions.get_by_id(row.reaction)
            atp_summary.append(
                [
                    side,
                    name_id_format(rxn),
                    f"{round(100 * row.percent, 2)}%",
                    round_format(row.flux),
                    equation_format(rxn),
                ]
            )
    return atp_summary, True


# Helper function for formating essential genes
def essential_genes_formatter(model, essential_genes):
    if not essential_genes:
        return json.dumps([])
    return json.dumps(
        [
            {
                "name": missing_format(gene.id),
                "essential": "Yes"
                if gene in essential_genes or gene.id in essential_genes
                else "No",
            }
            for gene in model.genes
        ]
    )


######################## REPORT FUNCTIONS ########################


def fba_report(
    model,
    fba_sol,
    fva_sol,
    essential_genes,
    model_id,
    media_id,
    export_html_path="fba_report.html",
):
    """Build an HTML report of an FBA solution and return it as a string.

    Parameters
    ----------
    model : cobra.Model
    fba_sol : cobra.Solution
        The solution the summary and reaction tabs describe.
    fva_sol : pandas.DataFrame or None
        ``cobra.flux_analysis.flux_variability_analysis`` of the model, with
        ``minimum`` and ``maximum`` columns; None leaves the reaction tabs empty.
    essential_genes : collection of cobra.Gene (or gene IDs), or None
    model_id, media_id : str
        Shown in the overview tab.
    export_html_path : str or None
        Where to write the report; None only returns it.
    """
    atp_summary, is_atp_summary = atp_summary_formatter(model, fba_sol)
    essential_genes = essential_genes or []
    # these key-value pairs are the variables-values that are substituted into the HTML report
    content = {
        "summary": model_summary(model, fba_sol),
        "atp_summary": {"is_atp_summary": is_atp_summary, "summary": atp_summary},
        "overview": [
            {"name": "Model", "value": model_id},
            {"name": "Media", "value": media_id},
            {"name": "Optimization status", "value": fba_sol.status},
            {"name": "Objective", "value": model.objective},
            {"name": "Objective value", "value": fba_sol.objective_value},
            {"name": "Number of reactions", "value": len(model.reactions)},
            {"name": "Number of compounds", "value": len(model.metabolites)},
        ],
        "reaction_tab": {
            "is_reactions": fva_sol is not None,
            "reactions": reaction_formater(model, fba_sol, fva_sol, ex=False),
            "help": "Select FVA setting and rerun to produce results.",
        },
        "ex_reaction_tab": {
            "is_reactions": fva_sol is not None,
            "reactions": reaction_formater(model, fba_sol, fva_sol, ex=True),
            "help": "Select FVA setting and rerun to produce results.",
        },
        "essential_genes_tab": {
            "is_essential_genes": len(essential_genes) > 0,
            "essential_genes": essential_genes_formatter(model, essential_genes),
            "help": "Select simulate all single KO to produce results.",
        },
    }
    return _render("fba_template.html", content, export_html_path)


def steadycom_report(flux_df, exMets_df, export_html_path="steadycom_report.html"):
    """HTML report of the two tables ``MSSteadyCom.interactions`` returns.

    The last ``len(flux_df.columns)`` rows of ``flux_df`` (the ``zz_``
    totals rows) become the "Total exchanged flux" tab."""
    total_table = flux_df.iloc[-len(flux_df.columns) :].copy()
    total_table.index = [i.replace("zz_", "") for i in total_table.index]
    flux_df = flux_df.iloc[: -len(flux_df.columns)]
    content = {
        "flux_table": flux_df.style.background_gradient().to_html(),
        "total_table": total_table.style.background_gradient().to_html(),
        "exchanged_mets": exMets_df.to_html(),
    }
    return _render("steadycom_template.html", content, export_html_path)


rm_costless = re.compile(r"(\s\(.+\))")


def remove_metadata(element):
    try:
        element = float(rm_costless.sub("", str(element)).replace("%", ""))
    except ValueError:
        pass
    return element


def convert_to_int(element):
    try:
        element = int(element)
    except (TypeError, ValueError, OverflowError):
        pass
    return element


_CATEGORY_FILES = ("sugars", "aminoAcids", "vitamins", "minerals", "energy_compounds")
_category_names = None


def _load_category_names():
    """{category: {compound id: name}} from data/categories/*.npy, read on first
    use rather than at import: energy_compounds.npy alone is about 60 MB."""
    global _category_names
    if _category_names is None:
        categories_dir = os.path.join(package_dir, "data", "categories")
        _category_names = {}
        for category in _CATEGORY_FILES:
            table = load(os.path.join(categories_dir, f"{category}.npy"))
            _category_names[category] = dict(zip(table[:, 0], table[:, 1]))
    return _category_names


def categorize_mets(metIDs):
    names = _load_category_names()
    categorized = {category: [] for category in _CATEGORY_FILES}
    met_other = []
    for metID in metIDs:
        for category in _CATEGORY_FILES:
            if metID in names[category]:
                categorized[category].append(f"{names[category][metID]} ({metID})")
                break
        else:
            met_other.append(metID)
    return (
        categorized["sugars"],
        categorized["aminoAcids"],
        categorized["vitamins"],
        categorized["minerals"],
        categorized["energy_compounds"],
        met_other,
    )


def process_mets(metIDs):
    return [", ".join(lst) for lst in categorize_mets(metIDs)]


_COMPARTMENT_SUFFIX = re.compile(r"_[a-z]+\d*$")
_MIP_COSTLESS = re.compile(r"(?<=\s\()(\d+)(?=\))")


def _costless_count(entry):
    """The parenthesised costless count of a "MIP (costless)" entry, "3 (1)" -> 1."""
    match = _MIP_COSTLESS.search(str(entry))
    return match.group() if match else ""


def commscores_report(
    df, mets, export_html_path="commscores_report.html", msdb_path=None
):
    """HTML report of the ``(df, mets)`` that ``CommScores`` computes.

    Score columns are read as they are present, so optional scores (CIP, FS,
    costless MIP) may be missing. Metabolite names come from the bundled
    ``data/cpdNames.json``, then from the ModelSEED database at ``msdb_path``
    when one is given; an ID without a known name is shown as itself. Nothing
    is written except ``export_html_path``.
    """
    from pandas import DataFrame, to_numeric

    with open(os.path.join(package_dir, "data", "cpdNames.json"), "r") as jsonIn:
        cpdNames = json.load(jsonIn)
    msdb = []  # loaded on the first name that cpdNames.json lacks

    def met_name(metID):
        base_id = _COMPARTMENT_SUFFIX.sub("", metID)
        for ID in (metID, base_id):
            if ID in cpdNames:
                return cpdNames[ID]
        if msdb_path is None:
            return metID
        if not msdb:
            from modelseedpy.biochem import from_local

            msdb.append(from_local(msdb_path))
        for ID in (metID, base_id):
            if ID in msdb[0].compounds:
                name = msdb[0].compounds.get_by_id(ID).name or metID
                cpdNames[metID] = name
                return name
        return metID

    # construct a heatmap
    df = df.copy()
    df.index.name = "Community_index"
    heatmap_df = df.copy(deep=True)
    heatmap_df.index = [
        f"{model1} ++ {model2}"
        for model1, model2 in zip(heatmap_df["model1"], heatmap_df["model2"])
    ]
    heatmap_df.index.name = "model1 ++ model2"
    if "media" in heatmap_df.columns:
        heatmap_df.index = [
            f"{models} in {media}"
            for models, media in zip(heatmap_df.index, heatmap_df["media"])
        ]
        heatmap_df.index.name = "model1 ++ model2 in Media"
    heatmap_df = heatmap_df.loc[~heatmap_df.index.duplicated(), :]
    for member in ("1", "2"):
        costless_col = f"MIP_model{member} (costless)"
        if costless_col in heatmap_df.columns:
            heatmap_df[f"c_MIP{member}"] = [
                _costless_count(e) if e not in [0, "0", ""] else ""
                for e in heatmap_df[costless_col]
            ]
            heatmap_df[f"MIP_model{member}"] = heatmap_df[costless_col]
    # TODO colorize the BIT entries as well
    heatmap_df = heatmap_df.drop(
        columns=[
            "model1",
            "model2",
            "media",
            "BIT",
            "MIP_model1 (costless)",
            "MIP_model2 (costless)",
        ],
        errors="ignore",
    )
    for col in heatmap_df.columns:
        heatmap_df[col] = to_numeric(
            heatmap_df[col].apply(remove_metadata), errors="coerce"
        )

    # construct a metabolites table
    met_columns = {
        "MRO": "MRO metabolites",
        "MIP model1": "MIP model1 metabolites",
        "MIP model2": "MIP model2 metabolites",
        "CIP": "CIP metabolites",
    }
    df_content = {}
    for label, key in met_columns.items():
        ids_column, names_column = [], []
        for met in mets:
            metIDs = [
                metID
                for metID in map(str, met.get(key) or [])
                if metID not in ["None", ""]
            ]
            ids_column.append(", ".join(metIDs))
            names_column.append(", ".join(met_name(metID) for metID in metIDs))
        df_content[f"{label} metabolite names"] = names_column
        df_content[f"{label} metabolite IDs"] = ids_column
    mets_table = DataFrame(data=df_content)
    mets_table.index.name = "Community_index"

    # populate the HTML template with the assembled simulation data from the DataFrame -> HTML conversion
    content = {
        "table": df.to_html(table_id="main", classes="display"),
        "mets_table": mets_table.to_html(),
        "heatmap": heatmap_df.round(3)
        .style.background_gradient()
        .format("{:g}", na_rep="")
        .set_table_attributes('class="display"')
        .to_html(),
    }
    return _render("commscores_template.html", content, export_html_path)
