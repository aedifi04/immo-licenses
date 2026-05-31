import adsk.core
import adsk.fusion
import traceback

CMD_ID = 'GenerativeDesignSetup'
CMD_NAME = 'Generative Design Sommaire'
CMD_DESC = (
    'Configure et lance une étude de conception générative: '
    'corps à préserver, obstacles, charges et contraintes.'
)
WORKSPACE_ID = 'FusionSolidEnvironment'
PANEL_ID = 'SolidCreatePanel'

_handlers = []

DIRECTIONS = {
    'Z- (vers le bas)': (0.0, 0.0, -1.0),
    'Z+ (vers le haut)': (0.0, 0.0, 1.0),
    'X-': (-1.0, 0.0, 0.0),
    'X+': (1.0, 0.0, 0.0),
    'Y-': (0.0, -1.0, 0.0),
    'Y+': (0.0, 1.0, 0.0),
}


def start():
    app = adsk.core.Application.get()
    ui = app.userInterface

    cmd_defs = ui.commandDefinitions
    existing = cmd_defs.itemById(CMD_ID)
    if existing:
        existing.deleteMe()

    cmd_def = cmd_defs.addButtonDefinition(CMD_ID, CMD_NAME, CMD_DESC)

    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    panel.controls.addCommand(cmd_def)

    handler = _GenerativeCreatedHandler()
    cmd_def.commandCreated.add(handler)
    _handlers.append(handler)


def stop():
    app = adsk.core.Application.get()
    ui = app.userInterface

    workspace = ui.workspaces.itemById(WORKSPACE_ID)
    panel = workspace.toolbarPanels.itemById(PANEL_ID)
    ctrl = panel.controls.itemById(CMD_ID)
    if ctrl:
        ctrl.deleteMe()

    cmd_def = ui.commandDefinitions.itemById(CMD_ID)
    if cmd_def:
        cmd_def.deleteMe()


class _GenerativeCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            cmd = args.command
            inputs = cmd.commandInputs

            # ── Corps à préserver ────────────────────────────────────────────
            preserve = inputs.addSelectionInput(
                'preserveBody',
                'Corps à préserver',
                'Corps de départ (la géométrie à optimiser)',
            )
            preserve.addSelectionFilter('SolidBodies')
            preserve.setSelectionLimits(1, 1)

            # ── Corps obstacles ──────────────────────────────────────────────
            obstacles = inputs.addSelectionInput(
                'obstacleBodies',
                'Corps obstacles (optionnel)',
                'Zones que la structure ne doit PAS occuper',
            )
            obstacles.addSelectionFilter('SolidBodies')
            obstacles.setSelectionLimits(0, 10)

            # ── Face de charge ───────────────────────────────────────────────
            force_face = inputs.addSelectionInput(
                'forceFace',
                'Face(s) de charge',
                'Face(s) sur lesquelles appliquer la force',
            )
            force_face.addSelectionFilter('Faces')
            force_face.setSelectionLimits(1, 5)

            # ── Magnitude de la force ────────────────────────────────────────
            inputs.addValueInput(
                'forceMagnitude',
                'Magnitude de force (N)',
                '',
                adsk.core.ValueInput.createByReal(1000.0),
            )

            # ── Direction de la force ────────────────────────────────────────
            dir_drop = inputs.addDropDownCommandInput(
                'forceDirection',
                'Direction de la force',
                adsk.core.DropDownStyles.LabeledIconDropDownStyle,
            )
            for label in DIRECTIONS:
                dir_drop.listItems.add(label, label == 'Z- (vers le bas)')

            # ── Face(s) fixe(s) ──────────────────────────────────────────────
            fixed_face = inputs.addSelectionInput(
                'fixedFace',
                'Face(s) fixe(s) / contraintes',
                'Face(s) immobiles (encastrement)',
            )
            fixed_face.addSelectionFilter('Faces')
            fixed_face.setSelectionLimits(1, 5)

            # ── Réduction de masse ───────────────────────────────────────────
            inputs.addValueInput(
                'massTarget',
                'Réduction de masse cible (%)',
                '',
                adsk.core.ValueInput.createByReal(60.0),
            )

            # ── Méthode de fabrication ───────────────────────────────────────
            mfg_drop = inputs.addDropDownCommandInput(
                'manufacturing',
                'Méthode de fabrication',
                adsk.core.DropDownStyles.LabeledIconDropDownStyle,
            )
            for label, selected in [
                ('Fraisage 2.5 axes', True),
                ('Fraisage 3 axes', False),
                ('Fraisage 5 axes', False),
                ('Impression 3D (sans support)', False),
                ('Impression 3D (avec support)', False),
                ('Coulée / moulage', False),
                ('Aucune contrainte', False),
            ]:
                mfg_drop.listItems.add(label, selected)

            # ── Matériau ────────────────────────────────────────────────────
            mat_drop = inputs.addDropDownCommandInput(
                'material',
                'Matériau',
                adsk.core.DropDownStyles.LabeledIconDropDownStyle,
            )
            for label, selected in [
                ('Acier (Steel)', True),
                ('Aluminium 6061', False),
                ('Titane Ti-6Al-4V', False),
                ('Nylon (PA12)', False),
            ]:
                mat_drop.listItems.add(label, selected)

            # ── Handler exécution ────────────────────────────────────────────
            handler = _GenerativeExecuteHandler()
            cmd.execute.add(handler)
            _handlers.append(handler)

        except Exception:
            adsk.core.Application.get().userInterface.messageBox(
                traceback.format_exc()
            )


class _GenerativeExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)

            if not design:
                ui.messageBox('Aucun document Fusion 360 actif.')
                return

            inputs = args.command.commandInputs
            preserve_sel = inputs.itemById('preserveBody')

            if preserve_sel.selectionCount == 0:
                ui.messageBox('Sélectionnez au moins un corps à préserver.')
                return

            preserve_body = adsk.fusion.BRepBody.cast(
                preserve_sel.selection(0).entity
            )
            force_mag = inputs.itemById('forceMagnitude').value
            force_dir_label = inputs.itemById('forceDirection').selectedItem.name
            mass_pct = inputs.itemById('massTarget').value
            mfg = inputs.itemById('manufacturing').selectedItem.name
            material = inputs.itemById('material').selectedItem.name
            obstacle_count = inputs.itemById('obstacleBodies').selectionCount
            force_face_count = inputs.itemById('forceFace').selectionCount
            fixed_face_count = inputs.itemById('fixedFace').selectionCount

            # Tentative via l'API Generative Design (Fusion 360 2.0.14700+)
            study_created = False
            try:
                gen_studies = design.generativeDesignStudies
                study = gen_studies.add()
                study.name = 'Étude Plugin GD'

                criteria = study.criteria

                col_preserve = adsk.core.ObjectCollection.create()
                col_preserve.add(preserve_body)
                criteria.preserveBodies = col_preserve

                if obstacle_count > 0:
                    col_obs = adsk.core.ObjectCollection.create()
                    for i in range(obstacle_count):
                        col_obs.add(
                            adsk.fusion.BRepBody.cast(
                                inputs.itemById('obstacleBodies').selection(i).entity
                            )
                        )
                    criteria.obstacleBodies = col_obs

                study_created = True

            except AttributeError:
                # API Generative Design non disponible dans cette version
                pass

            dx, dy, dz = DIRECTIONS[force_dir_label]
            summary = (
                '══════════════════════════════════\n'
                ' CONFIGURATION GÉNÉRATIVE DESIGN\n'
                '══════════════════════════════════\n\n'
                '  Corps préservé   : {preserve}\n'
                '  Obstacles        : {obs} corps\n'
                '  Faces de charge  : {ff} face(s)\n'
                '  Faces fixes      : {fixed} face(s)\n\n'
                '  Force            : {mag:.0f} N  [{dir}]  ({dx:.0f}, {dy:.0f}, {dz:.0f})\n'
                '  Réduction masse  : {mass:.0f} %\n'
                '  Fabrication      : {mfg}\n'
                '  Matériau         : {mat}\n\n'
                '{status}'
            ).format(
                preserve=preserve_body.name,
                obs=obstacle_count,
                ff=force_face_count,
                fixed=fixed_face_count,
                mag=force_mag,
                dir=force_dir_label,
                dx=dx, dy=dy, dz=dz,
                mass=mass_pct,
                mfg=mfg,
                mat=material,
                status=(
                    '✓ Étude créée via l\'API (nom: "Étude Plugin GD").\n'
                    '  → Allez dans l\'espace Generative Design\n'
                    '     pour finaliser les charges et générer.'
                    if study_created else
                    '  ► L\'API Generative Design n\'est pas disponible\n'
                    '     dans cette version de Fusion 360.\n\n'
                    '  Pour lancer manuellement :\n'
                    '  1. Conception > Espace Générativ Design\n'
                    '  2. Nouvelle étude — coller les paramètres ci-dessus\n'
                    '  3. Pré-vérification → Générer'
                ),
            )

            ui.messageBox(summary, 'Generative Design — Plugin')

        except Exception:
            adsk.core.Application.get().userInterface.messageBox(
                traceback.format_exc()
            )
