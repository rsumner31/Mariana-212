import inspect, sys, os, shutil
import Mariana.HTML_Templates.template as MTMP

class Vulcan(MTMP.HTMLTemplate_ABC):
    """A theme"""
    def __init__(self):
        super(Vulcan, self).__init__()
        self.dirname = os.path.dirname(inspect.getfile(sys.modules[__name__]))
        
        f = open(os.path.join(self.dirname, "vulcan.html"))
        self.html = f.read()
        f.close()
        
        self.jsFP = os.path.join(self.dirname, "vulcan.js")
        f = open(self.jsFP)
        self.js = f.read()
        f.close()
        
        self.cssFP = os.path.join(self.dirname, "vulcan.css")
        f = open(self.cssFP)
        self.css = f.read()
        f.close()

    def formatNotes(self, notes) :
        tmp = """
            <div class="uk-flex-center uk-child-width-1-2@s uk-child-width-1-3@m" uk-grid>
               {trs} 
            </div>
        """

        tmpTrs ="""
            <div class="uk-card uk-card-default uk-card-small uk-card-body">
                <h3 class="uk-card-title">{title}</h3>
                <p>{text}</p>
            </div>
        """
        
        trs = []
        for k, v in notes.iteritems() :
            trs.append(tmpTrs.format(title = k, text = v))
       
        return tmp.format(trs = "\n".join(trs))

    def render(self, filename, networkJson) :
        import time
        import json

        title = os.path.basename(filename)
        currFolder = os.path.dirname(filename)

        layers = []
        for l in networkJson["layers"] :
            dct = {"name": l, "shape": networkJson["layers"][l]['shape'], "level": networkJson["layers"][l]['level']}

            for cat in ["parameters", "hyperParameters", "notes"] :
                dct[cat] = {"size": 0}
                dct[cat]["layer"] = []
                for pName, pVal in networkJson["layers"][l][cat].iteritems() :
                    if cat == "notes" :
                        pKey = pName
                    else :
                        pKey = "%s.%s" % (l, pName)

                    dct[cat]["layer"].append({"name": pKey, "value": pVal})
                    dct[cat]["size"] += 1
                    
                for absCat, abstractions in networkJson["layers"][l]["abstractions"].iteritems() :
                    dct[cat][absCat] = []
                    for absName, absVal in abstractions.iteritems() :
                        for pName, pVal in absVal[cat].iteritems() :
                            if cat == "notes" :
                                pKey = pName
                            else :
                                pKey = "{absName}.{pName}".format(absName = absName, pName = pName)
                            
                            dct[cat][absCat].append({"name": pKey, "value": pVal})
                            dct[cat]["size"] += 1
    
            layers.append([l, dct])

        html = self.html.format(
            TITLE=title,
            MODEL_NOTES=self.formatNotes(networkJson["notes"]),
            MACHINE_TIME=time.time(),
            USER_TIME=time.ctime().replace("_", " "),
            LAYERS_JSON=json.dumps(layers),
            EDGES_JSON=json.dumps(networkJson["edges"])
        )
        
        webFolder = "%s_web" % title
        if not os.path.exists(webFolder) :
            os.mkdir(webFolder)

        shutil.copy(self.jsFP, os.path.join(currFolder, webFolder, "vulcan.js"))
        shutil.copy(self.cssFP, os.path.join(currFolder, webFolder, "vulcan.css"))
        
        f = open(os.path.join(currFolder, "%s.html" % title), "w") 
        f.write(html)
        f.close()