KeysDictionary("apogee", (1,2), *(
    # Misc
    Key("text", String(), help="text for humans"),
    Key("version", String(), help="version string derived from svn info."),

    # Camera
    Key("arrayPower",
        Bool("off", "on", invalid="?"),
        help="Commanded array power."),
    Key("cameraState",
        Enum("Exposing", "Done", "Stopping", "Stopped", "Failed", name="expState", help="state of exposure"),
        help="A simplified version of exposureState that is output by the status command",
    ),
    Key("dspFiles",
        String()*(1,10),
        help="List of available DSP files"),
    Key("dspload",
        String(),
        help="Name of DSP file currently in use"),
    Key("exposureState",
        Enum("Exposing", "Done", "Stopping", "Stopped", "Failed", name="expState", help="state of exposure"),
        String(name="expType", help="type of exposure (object argument)"),
        Int(name="nReads", help="total number of UTR reads requested"),
        String(name="expName", help="name of exposure"),
    ),

    # Collimator
    Key("collOrient",
        Float(name="piston", units="microns", invalid="NaN", help="+ brings collimator towards the instrument"),
        Float(name="pitch", units="pixels", invalid="NaN", help="+ tips the beam down"),
        Float(name="yaw", units="pixels", invalid="NaN", help="+ tips the beam to the right as seen by the collimator"),
        help="Collimator orientation"),
    Key("collMountPosition",
        Float(units="microns", invalid="NaN")*3,
        help="Current collimator actuator position"),
    Key("collMountLimits",
        Float(units="microns", invalid="NaN")*2,
        help="Reverse, forward software limits for collimator actuator position"),
    Key("collLimitSwitch",
        Bool("false", "true", invalid="?")*6,
        help="Home 1, forward 1, home 2, forward 2, home 3, forward 3 limit switch activated?"),

    )
)
