from collections import OrderedDict
from wrappers import TheanoFunction
import Mariana.settings as MSET
import Mariana.abstraction as MABS

import cPickle, pickle

__all__= ["loadModel", "Network"]

def loadModel(filename) :
    """Shorthand for Network.load"""
    return Network.load(filename)

class Network(MABS.Logger_ABC) :
    """All theano functions of all layers are accessible through the network interface **network.x(...)**."""
    def __init__(self) :
        super(Network, self).__init__()

        self.inputs = OrderedDict()
        self.layers = OrderedDict()
        self.outputs = OrderedDict()
        self.layerAppelidos = {}
    
        self.edges = OrderedDict()
        
        self.outConnections = OrderedDict()
        self.inConnections = OrderedDict()
        self.notes = OrderedDict()

        self.parameters = []
        self.parameterStash = {}

        self._mustInit = True
        # self.outputMaps = {}

    def getOutputs(self) :
        """return network outputs"""
        return self.outputs

    def getInputs(self) :
        """return network inputs"""
        return self.inputs

    def getLog(self) :
        """get the log"""
        log = {
            "network": self.log,
            "layers": {}
        }

        for name, l in self.layers.iteritems() :
            log["layers"][name]  = l.getLog()

        return log

    def addNote(self, title, text) :
        """add a note"""
        self.notes[title] = text

    def getInConnections(self, layer) :
        """return a layer's incoming connections"""
        return list(self.inConnections[layer])
    
    def getOutConnections(self, layer) :
        """return a layer's out connections"""
        return list(self.outConnections[layer])

    def _addEdge(self, layer1Name, layer2Name) :
        """Add a connection between two layers"""

        layer1 = self.layers[layer1Name]
        layer2 = self.layers[layer2Name]

        self.edges[ (layer1.name, layer2.name) ] = (layer1, layer2)

        try :
            self.outConnections[layer1].add(layer2)
        except :
            self.outConnections[layer1] = set([layer2])

        try :
            self.inConnections[layer2].add(layer1)
        except :
            self.inConnections[layer2] = set([layer1])

        self.logEvent("New edge %s > %s" % (layer1.name, layer2.name))

    def _addLayer(self, h) :
        """adds a layer to the network"""
        
        try :
            if self.layerAppelidos[h.name] != h.appelido :
                raise ValueError("There's already a layer by the name of '%s'" % (h.name))
        except KeyError :
            self.layerAppelidos[h.name] = h.appelido
        
        self.layers[h.name] = h
        try :
            self.inConnections[h] = self.inConnections[h].union(h.network.inConnections[h])
            self.outConnections[h] = self.outConnections[h].union(h.network.outConnections[h])
        except KeyError :
            try :
                self.inConnections[h] = h.network.inConnections[h]
                self.outConnections[h] = h.network.outConnections[h]
            except KeyError :
                self.inConnections[h] = set()
                self.outConnections[h] = set()

    def merge(self, fromLayer, toLayer) :
        """Merges the networks of two layers together. fromLayer must be part of the self"""
        
        self.logEvent("Merging nets: %s and %s" % (fromLayer.name, toLayer.name))

        if fromLayer.name not in self.layers :
            raise ValueError("from layer '%s' is not part of this network" % fromLayer.name)

        newLayers = toLayer.network.layers.values()
        for l in newLayers :
            self._addLayer(l)

        for e in toLayer.network.edges.iterkeys() :
            self._addEdge(e[0], e[1])

        self._addEdge(fromLayer.name, toLayer.name)
        
        for l in newLayers :
            l.network = self

        for name, layer in self.layers.iteritems() :
            self.logEvent("Registering layer %s" % (layer.name))

    def initParameters(self) :
        """Initializes the parameters of all layers but does nothing else.
        Call this before tying parameters together::
        
            model = i > h > o
            model.initParameters()
            h.W = o.W.T

            model.train(...)
        """
        for l in self.layers.itervalues() :
            l.initParameters()

    def init(self, force=False) :
        "Initialiases the network by initialising every layer."
        for layer in self.layers.itervalues() :
            layerTypes = layer.getTypes()
            if MSET.TYPE_INPUT_LAYER in layerTypes:
                self.inputs[layer.name] = layer
            if MSET.TYPE_OUTPUT_LAYER in layerTypes:
                self.outputs[layer.name] = layer
        
        if self._mustInit or force :
            self.logEvent("Initialization begins!")
            print("\n" + MSET.OMICRON_SIGNATURE)

            if len(self.inputs) < 1 :
                raise ValueError("Network has no inputs")

            for inp in self.inputs.itervalues() :
                inp._initA(force=True)

            for l in self.layers.itervalues() :
                # print l._initStatus
                l._initB(force=True)
                self.parameters = self.getFullParameters()
    
            self._mustInit = False
    
    def save(self, filename) :
        """Save a model on disk"""
        res = {
            'network': {
                "edges": self.edges.keys(),
                "log": self.log,
                "notes": self.notes
            },
            'layers': {}
        }

        for l in self.layers.itervalues() :
            l._resetNetwork(fullReset = False)
            res["layers"][l.name] = l
                
        ext = '.mar'
        if filename.find(ext) < 0 :
            fn = filename + ext
        else :
            fn = filename

        f = open(fn, 'wb', pickle.HIGHEST_PROTOCOL)
        cPickle.dump(res, f)
        f.close()

        for l in self.layers.itervalues() :
            l._resetNetwork(fullReset = False, newNetwork = self)

    @classmethod
    def load(cls, filename) :
        """Load a model from disk"""
        
        f = open(filename)
        pkl = cPickle.load(f)
        f.close()

        for l1, l2 in pkl["network"]["edges"] :
            network = pkl["layers"][l1] > pkl["layers"][l2]

        network.log = pkl["network"]["log"]
        network.notes = pkl["network"]["notes"]

        return network

    def toInputs(self, toConvert) :
        """returns a similar network with layers in toConvert transformed as inputs, toConvert must be a list of layer names."""
        layers = {}

        for l in self.layers.itervalues() :
            if l.name in toConvert :
                ll = l.toInput()
            else :
                ll = l.clone()

            layers[l.name] = ll

        for l1, l2 in self.edges() :
            network = layers[l1] > layers[l2]
        
        # network.log = self.log
        # network.notes = self.notes

        return network

    def toDOT(self, name, forceInit = True) :
        """returns a string representing the network in the DOT language.
        If forceInit, the network will first try to initialize each layer
        before constructing the graph"""

        import time

        if forceInit :
            self.init()

        com = "//Mariana network DOT representation generated on %s" % time.ctime()
        s = '#COM#\ndigraph "%s"{\n#HEAD#;\n\n#GRAPH#;\n}' % name

        headers = []
        aidi = 0
        aidis = {}
        for l in self.layers.itervalues() :
            aidis[l.name] = "layer%s" % aidi
            headers.append("\t" + aidis[l.name] + l._dot_representation())
            aidi += 1

        g = []
        for e in self.edges :
            g.append("\t%s -> %s" % (aidis[e[0]], aidis[e[1]]))

        s = s.replace("#COM#", com)
        s = s.replace("#HEAD#", ';\n'.join(headers))
        s = s.replace("#GRAPH#", ';\n'.join(g))
        s = s.replace("-", '_')

        return s

    def toDictionary(self, name) :
        """return a dict representation of the network"""
        def do(dct, layer, level) :
            dct[layer.name] = layer.toDictionary()
            dct[layer.name]["level"] = level
            for  lin in self.inConnections[layer] :
                if lin.name in dct :
                    dct[layer.name]["level"] = max(dct[lin.name]["level"]+1, dct[layer.name]["level"])
             
            dct[layer.name]["abstractions"] = OrderedDict()
            for k, v in layer.abstractions.iteritems() :
                dct[layer.name]["abstractions"][k] = OrderedDict()
                if type(v) is list :
                    for vv in v :
                        dct[layer.name]["abstractions"][k][vv.__class__.__name__] = vv.toDictionary()
                else :
                    dct[layer.name]["abstractions"][k][v.__class__.__name__] = v.toDictionary()

            for l2 in self.outConnections[layer] :
                dct.update(do(dct, l2, level+1) )
            
            return dct

        res = {}
        res["layers"] = OrderedDict()

        levels = {}
        for layerName, layer in self.inputs.iteritems() :
            res["layers"].update(do(res["layers"], layer, 0))

        res["edges"] = []
        for t, f in self.edges.iterkeys() :
            res["edges"].append({"from": t, "to": f})

        res["name"] = name
        res["notes"] = self.notes

        return res

    def getFullParameters(self) :
        """get all model parameters"""
        if self._mustInit :
            params = {}
            for layer in self.layers.itervalues() :
                for k, v in layer.getFullParameters().iteritems() :
                    params["%s.%s" % (layer.name, k)] = v
            return params
        else :
            return self.parameters

    def stashParameters(self, stashName, forceReset=False) :
        import numpy
        """Saves parameters in memory"""
        if stashName not in self.parameterStash or forceReset :
            self.parameterStash[stashName] = {}
            for k, v in self.getFullParameters().iteritems() :
                if v.isShared() :
                    self.parameterStash[stashName][k] = v.getValue()
        else :
            params = self.getFullParameters()
            for k in self.parameterStash[stashName].iterkeys() :
                self.parameterStash[stashName][k] = params[k].getValue()

    def applyStash(self, stashName) :
        """set parameters to stash values"""
        params = self.getFullParameters()
        for k, v in self.parameterStash[stashName].iteritems() :
            params[k].setValue(v)
        self._mustInit = True

    def saveStash(self, modelName, stashName) :
        """Saves stashed parameters to disk"""
        fn = "%s-%s.stash.mar.pkl" %(modelName, stashName)
        f = open(fn, 'wb', pickle.HIGHEST_PROTOCOL)
        cPickle.dump(self.parameterStash[stashName], f)
        f.close()

    def loadStash(self, filename) :
        """Load a stash from disk"""
        f = open(filename)
        stash = cPickle.load(f)
        f.close()

        return stash

    def dropStash(self, stashName) :
        """drops a stash"""
        del self.parameterStash[stashName]

    def earseAllStashes(self) :
        """erases all stashes"""
        self.parameterStash = {}

    def toJson(self, name, pretty=True) :
        import json
        """return a json representation of the network"""
        if pretty :
            return json.dumps(self.toDictionary(name), indent=2, sort_keys=True)
    
        return json.dumps(self.toDictionary(name))

    def saveHTML(self, name, init=True) :
        from Mariana.HTML_Templates.vulcan.vulcan import Vulcan
        if init :
            self.init()
        template = Vulcan()
        template.render(name, self.toDictionary(name))

    def saveHTML_old(self, name, forceInit = True) :
        """Creates an HTML file with the graph representation."""
        from Mariana.HTML_Templates.aqua import getHTML
        import time
        temp = getHTML(self.toDOT(name, forceInit), name, time.ctime())
        f = open(name + '.mariana.dot.html', 'wb')
        f.write(temp)
        f.close()

    def saveDOT(self, name, forceInit = True) :
        "saves the current network as a graph in the DOT format into the file name.mariana.dot"
        f = open(name + '.mariana.dot', 'wb')
        f.write(self.toDOT(name, forceInit))
        f.close()

    def __contains__(self, layerName) :
        """Is there a layer by that name"""
        return layerName in self.layers

    def __getitem__(self, l) :
        """get a layer by name"""
        try :
            return self.layers[l]
        except KeyError :
            raise KeyError("There's no layer named: '%s'" % l)

    def __repr__(self) :
        if self._mustInit :
            return "< Mariana Network (not initialized) (%s layers) >" % (len(self.layers))
        else :
            return "< Mariana Network (%s layers): %s > ... > [%s] >" % (len(self.layers), self.inputs.keys(), self.outputs.keys())

    # def __getattribute__(self, k) :
    #     """
    #     All theano functions are accessible through the network interface network.x(). Here x is called a model function.
    #     """
    #     try :
    #         return object.__getattribute__(self, k)
    #     except AttributeError as e :
    #         # a bit too hacky, but solves the following: Pickle asks for attribute not found in networks which triggers initializations
    #         # of free outputs, and then theano complains that the layer.outputs are None, and everything crashes miserably. 
    #         if k == "__getstate__" or k == "__slots__" :
    #             raise e
            
    #         outs = object.__getattribute__(self, 'outputs')
    #         init = object.__getattribute__(self, 'init')
    #         init()

    #         maps = object.__getattribute__(self, 'outputMaps')
    #         try :
    #             return maps[k]
    #         except KeyError :
    #             raise e
    
